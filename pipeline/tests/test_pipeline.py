import json
import sqlite3

from regstudio import config, drafting, extract, intake, reader, registry, triage
from regstudio.registry import split_clauses


def _db():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def run_all():
    intake.run(); extract.run(); registry.run(); triage.run(); reader.run(); drafting.run()


def test_intake_is_idempotent(env):
    assert len(intake.run().added) == 2
    again = intake.run()
    assert again.added == [] and again.duplicates == 2


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
    assert stages == {"regulation": "registered", "order": "drafted"}
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
