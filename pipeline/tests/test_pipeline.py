import json

import pytest
import sqlite3

from regstudio import config, drafting, extract, intake, reader, registry, triage
from regstudio.registry import split_clauses


def _db():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def run_all():
    from regstudio import amend
    intake.run(); extract.run(); registry.run(); amend.run(); triage.run(); reader.run(); drafting.run()


def test_intake_is_idempotent(env):
    assert len(intake.run().added) == 3
    again = intake.run()
    assert again.added == [] and again.duplicates == 3


def test_intake_rejects_bad_hash(env):
    meta = next((env / "inbox").rglob("*.json"))
    m = json.loads(meta.read_text()); m["sha256"] = "0" * 64
    meta.write_text(json.dumps(m))
    r = intake.run()
    assert len(r.rejected) == 1 and "sha256" in r.rejected[0][1]


def test_clause_split_handles_hyphenated_headings():
    out = split_clauses([{"pid": "p1.1", "text": "9. Cross-subsidy surcharge.- (1) Shall not exceed."},
                         {"pid": "p1.2", "text": "(2) Not for captive users."}])
    assert [c["number"] for c in out] == ["9", "9(1)", "9(2)"]
    assert out[0]["heading"] == "Cross-subsidy surcharge"


def test_pipeline_end_to_end(env):
    run_all()
    c = _db()
    stages = dict(c.execute("SELECT doc_type, stage FROM documents").fetchall())
    assert stages == {"regulation": "registered", "amendment": "registered", "order": "drafted"}
    links = c.execute("SELECT * FROM links").fetchall()
    assert all(l["status"] == "proposed" for l in links)
    resolved = {l["target_id"] for l in links if l["resolved"]}
    assert any(t.endswith("/8(3)") for t in resolved)
    assert "ea2003/s86" in resolved
    unresolved = [l for l in links if not l["resolved"]]
    assert unresolved and all(l["target_id"] is None for l in unresolved)


def test_reader_drops_references_it_cannot_ground(env):
    intake.run(); extract.run(); registry.run()
    c = _db()
    paras = {"p1.8": "The petitioner relies on Regulation 8(3)."}
    refs = [
        {"citation_text": "Regulation 8(3)", "link_type": "applies", "target_kind": "clause",
         "target_id": "made/up/id", "pid": "p1.8", "excerpt": "relies on Regulation 8(3)"},
        {"citation_text": "Regulation 9", "link_type": "applies", "target_kind": "clause",
         "target_id": None, "pid": "p9.9", "excerpt": "x"},
        {"citation_text": "Regulation 8", "link_type": "applies", "target_kind": "clause",
         "target_id": None, "pid": "p1.8", "excerpt": "words that are not there"},
    ]
    kept, dropped = reader.check_references(c, refs, paras)
    assert len(kept) == 1 and kept[0]["target_id"] is None and kept[0]["resolved"] == 0
    assert len(dropped) == 2


def test_line_fragments_merge_into_paragraphs():
    from regstudio.extract import _merge_lines
    blocks = [("2. Regulation 9(7) provides for settlement of a deficit. In terms of the said", [50, 100, 500, 112]),
              ("provision, any deficit is shared.", [50, 114, 300, 126]),
              ("16.09.2024, except for Regulation 8(8).", [50, 128, 300, 140]),
              ("3. The extract is as follows:", [50, 160, 300, 172]),
              ("(i) first item", [50, 174, 300, 186])]
    out = _merge_lines(blocks)
    assert [t[:2] for t, _ in out] == ["2.", "3.", "(i"]
    assert "16.09.2024" in out[0][0]


def test_regulation_ids_are_readable():
    from regstudio.registry import regulation_id
    title = "Central Electricity Regulatory Commission (Deviation Settlement Mechanism and Related Matters) Regulations, 2024"
    assert regulation_id("cerc", title, "2024-08-05") == "cerc/deviation-settlement-mechanism-related-matters-2024"


def test_check_inbox_reports_without_registering(env):
    from regstudio import intake as ik
    bad = env / "inbox" / "rerc" / "2026-11-09" / "stray.json"
    bad.write_text("{}")
    (env / "inbox" / "loose.pdf").write_bytes(b"%PDF-1.4")
    report = ik.check()
    assert report["valid"] == 3
    assert report["metadata_without_pdf"] == ["rerc/2026-11-09/stray.json"]
    assert report["misplaced_files"] == ["loose.pdf"]
    assert _db().execute("SELECT count(*) FROM documents").fetchone()[0] == 0


def test_amendment_changes_are_proposed_then_applied_with_history(env):
    from regstudio import amend
    intake.run(); extract.run(); registry.run(); amend.run()
    c = _db()
    changes = c.execute("SELECT * FROM amendment_changes ORDER BY id").fetchall()
    assert {(ch["clause_number"], ch["action"]) for ch in changes} == {("8(3)", "substitute"), ("9(2)", "omit")}
    assert all(ch["status"] == "proposed" for ch in changes)
    reg = c.execute("SELECT id FROM regulations").fetchone()[0]
    # Registry untouched until a reviewer applies a change.
    before = c.execute("SELECT text FROM clauses WHERE id = ?", (f"{reg}/8(3)",)).fetchone()[0]
    with pytest.raises(amend.ApplyError):
        amend.apply_change(c, changes[0]["id"], "Test Reviewer")  # principal regulation not yet set
    c.execute("UPDATE amendment_changes SET regulation_id = ?, effective_date = '2026-12-01'", (reg,))
    for ch in changes:
        amend.apply_change(c, ch["id"], "Test Reviewer")
    c.commit()
    sub = c.execute("SELECT text, in_force_from FROM clauses WHERE id = ?", (f"{reg}/8(3)",)).fetchone()
    assert "any other time block" in sub["text"] and sub["in_force_from"] == "2026-12-01"
    old = c.execute("SELECT text, in_force_to FROM clause_versions WHERE clause_id = ?", (f"{reg}/8(3)",)).fetchone()
    assert old["text"] == before and old["in_force_to"] == "2026-11-30"
    assert c.execute("SELECT in_force_to FROM clauses WHERE id = ?", (f"{reg}/9(2)",)).fetchone()[0] == "2026-11-30"
    with pytest.raises(amend.ApplyError):
        amend.apply_change(c, changes[0]["id"], "Test Reviewer")  # already applied


def test_broken_ligature_map_is_repaired_only_when_present():
    from regstudio.extract import repair_ligatures
    broken = ["This Petition has been Niled by the Petitioner.", "The Rules are notiNied and speciTied.",
              "The beneNits and modiNications, Nirst and Ninal.", "BrieTly stated, the Nlow is sufNicient.",
              "Nigam Limited, Nimesh Patel and Nisarg; Till date.", "The Nixed charge is Tit."]
    out, n = repair_ligatures(broken)
    assert out == ["This Petition has been filed by the Petitioner.", "The Rules are notified and specified.",
                   "The benefits and modifications, first and final.", "Briefly stated, the flow is sufficient.",
                   "Nigam Limited, Nimesh Patel and Nisarg; Till date.", "The fixed charge is fit."]
    clean = ["Nigam Limited filed the petition before NLDC.", "Mr. Nimesh Patel appeared. Till then."]
    assert repair_ligatures(clean) == (clean, 0)


def test_bilingual_gazette_uses_english_version():
    from regstudio.registry import english_part, split_clauses
    paras = [{"pid": "p1.1", "text": "5. जीईओए आवेदन के लिये पात्रता मानदंड इन विनियमों के प्रावधान"},
             {"pid": "p1.2", "text": "7. विद्यमान उपभोक्ताओं के लिये संव्यवहार"},
             {"pid": "p2.1", "text": "5. Eligibility criteria for GEOA application (i) Subject to these Regulations"},
             {"pid": "p2.2", "text": "7. Treatment for existing consumers Existing consumers may continue."},
             {"pid": "p2.3", "text": "Rajasthan Electricity Regulatory Commission, Jaipur"}]
    kept = english_part(paras)
    assert [p["pid"] for p in kept] == ["p2.1", "p2.2", "p2.3"]
    assert {c["number"]: c["pid"] for c in split_clauses(kept)}["7"] == "p2.2"
    english_only = paras[2:]
    assert english_part(english_only) == english_only


def test_running_heads_merged_into_first_paragraph_are_removed():
    from regstudio.extract import strip_running_heads
    paras = []
    for page in range(1, 7):
        head = (f"भाग 7 राजस्थान राज-पत्र, जुलाई 17, 2025 {100 + page}" if page % 2
                else f"{100 + page} राजस्थान राज-पत्र, जुलाई 17, 2025 भाग 7")
        topic = ["Short title", "Definitions", "Eligibility", "Nodal agency", "Charges", "Banking"][page - 1]
        paras.append({"pid": f"p{page}.1", "text": f"{head} {page}. {topic} Text."})
        paras.append({"pid": f"p{page}.2", "text": "Provided that the body continues."})
    out = strip_running_heads(paras)
    assert out[0]["text"] == "1. Short title Text."
    assert out[2]["text"] == "2. Definitions Text."
    assert out[1]["text"] == "Provided that the body continues."
    openings = ["The Commission heard the parties", "Provided that the licensee shall", "In the matter of",
                "Having considered the submissions", "Accordingly, the petition is"]
    plain = [{"pid": f"p{i}.1", "text": f"{openings[i - 1]} on page {i}"} for i in range(1, 6)]
    assert strip_running_heads(plain) == plain
