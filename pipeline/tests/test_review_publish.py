"""Review screen and publish rules: nothing unapproved leaves, and every approval names a reviewer."""

import http.cookiejar
import json
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest
import uvicorn

from regstudio import config, drafting, extract, intake, publish, reader, registry, triage


def _db():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture()
def server(env):
    intake.run(); extract.run(); registry.run(); triage.run(); reader.run(); drafting.run()
    from regstudio.review_app import app
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def post(path, data):
        try:
            return opener.open(f"http://127.0.0.1:{port}{path}", urllib.parse.urlencode(data, doseq=True).encode()).status
        except urllib.error.HTTPError as e:
            return e.code

    def get(path):
        with opener.open(f"http://127.0.0.1:{port}{path}") as r:
            return r.read().decode("utf-8")

    post.get = get  # page text, using the same signed-in cookie jar
    post.url = f"http://127.0.0.1:{port}"
    yield post
    srv.should_exit = True
    t.join(timeout=5)


def _ids():
    c = _db()
    doc = c.execute("SELECT doc_id FROM orders").fetchone()[0]
    reg = c.execute("SELECT id FROM regulations").fetchone()[0]
    links = c.execute("SELECT id, target_id FROM links ORDER BY id").fetchall()
    return doc, reg, links


def test_nothing_is_approved_without_a_named_reviewer(server):
    doc, _, links = _ids()
    assert server(f"/order/{doc}/summary", {"action": "approve", "summary": "x"}) == 403
    assert server(f"/link/{links[0]['id']}", {"action": "approve"}) == 403
    assert _db().execute("SELECT count(*) FROM links WHERE status = 'approved'").fetchone()[0] == 0


def test_unresolved_link_cannot_be_approved_without_a_target(server):
    _, _, links = _ids()
    server("/whoami", {"name": "Test Reviewer"})
    unresolved = next(l for l in links if l["target_id"] is None)
    assert server(f"/link/{unresolved['id']}", {"action": "approve"}) == 400
    assert server(f"/link/{unresolved['id']}", {"action": "approve", "target": "clause::made/up"}) == 400
    row = _db().execute("SELECT status, reviewer FROM links WHERE id = ?", (unresolved["id"],)).fetchone()
    assert row["status"] == "proposed" and row["reviewer"] is None


def test_publish_releases_only_approved_items(server):
    doc, reg, links = _ids()
    out = publish.run()
    assert out["orders"] == 0 and out["regulations"] == 0  # nothing approved yet

    server("/whoami", {"name": "Test Reviewer"})
    resolved = [l for l in links if l["target_id"]]
    # Approve one link before its clause is approved: it must be held back.
    assert server(f"/link/{resolved[0]['id']}", {"action": "approve"}) == 303
    assert server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed summary.",
                                            "issue": "i", "outcome": "o"}) == 303
    out = publish.run()
    assert out["orders"] == 1 and out["links_held_back"] == 1
    order = json.loads((config.SNAPSHOT / "orders.json").read_text())[0]
    assert order["links"] == [] and order["reviewed_by"] == "Test Reviewer"

    # Approving the regulation releases the link.
    assert server(f"/regulation/{reg}/meta", {"title": "Sample regulation", "action": "approve"}) == 303
    out = publish.run()
    assert out["links_held_back"] == 0
    order = json.loads((config.SNAPSHOT / "orders.json").read_text())[0]
    assert len(order["links"]) == 1 and order["links"][0]["pid"]


def test_publish_clean_drops_sample_data(server):
    doc, reg, _ = _ids()
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/regulation/{reg}/meta", {"title": "Sample regulation", "action": "approve"})
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed summary.", "issue": "i", "outcome": "o"})
    assert publish.run()["orders"] == 1
    assert json.loads((config.SNAPSHOT / "site.json").read_text())["contains_sample_data"] is True
    out = publish.run(clean=True)
    assert out["orders"] == 0 and out["regulations"] == 0
    assert json.loads((config.SNAPSHOT / "site.json").read_text())["contains_sample_data"] is False


def test_every_approval_is_audited(server):
    doc, _, _ = _ids()
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed summary.", "issue": "i", "outcome": "o"})
    rows = _db().execute("SELECT actor, action FROM audit WHERE action LIKE 'summary.%'").fetchall()
    assert [(r["actor"], r["action"]) for r in rows] == [("Test Reviewer", "summary.approve")]


def test_reviewer_sets_the_public_title(server):
    doc, _, _ = _ids()
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/order/{doc}/summary", {"action": "save", "summary": "s", "title": "Plain-English title"})
    assert _db().execute("SELECT title FROM documents WHERE id = ?", (doc,)).fetchone()[0] == "Plain-English title"


def test_sign_in_required_once_reviewers_exist(server):
    from regstudio import auth
    doc, _, _ = _ids()
    auth.add_reviewer("Legal One", "correct horse battery")
    assert server("/whoami", {"name": "Anyone"}) in (303, 403)  # redirected to sign-in or refused
    assert server(f"/order/{doc}/summary", {"action": "approve", "summary": "x"}) == 303  # redirect to /login
    assert _db().execute("SELECT summary_status FROM orders").fetchone()[0] == "proposed"
    assert server("/login", {"name": "Legal One", "password": "wrong password"}) == 401
    assert server("/login", {"name": "Legal One", "password": "correct horse battery"}) == 303
    assert server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"}) == 303
    assert _db().execute("SELECT reviewer FROM orders").fetchone()[0] == "Legal One"


def test_amendment_page_and_history_publish(server):
    from regstudio import amend
    amend.run()
    c = _db()
    doc = c.execute("SELECT id FROM documents WHERE doc_type = 'amendment'").fetchone()[0]
    reg = c.execute("SELECT id FROM regulations").fetchone()[0]
    server("/whoami", {"name": "Test Reviewer"})
    assert server(f"/amendment/{doc}/meta", {"regulation_id": reg, "effective_date": "2026-12-01"}) == 303
    for (cid,) in c.execute("SELECT id FROM amendment_changes").fetchall():
        assert server(f"/amendment-change/{cid}", {"action": "apply"}) == 303
    server(f"/regulation/{reg}/meta", {"title": "Sample regulation", "action": "approve"})
    publish.run()
    clauses = {x["number"]: x for x in json.loads((config.SNAPSHOT / "clauses.json").read_text())}
    assert len(clauses["8(3)"]["versions"]) == 1 and clauses["8(3)"]["in_force_from"] == "2026-12-01"
    assert clauses["9(2)"]["in_force_to"] == "2026-11-30"


def test_queue_shows_commission_website_health(server):
    (config.STORE / "download_last.json").write_text(json.dumps({"at": "2026-11-11T22:00", "sites": {
        "kerc": {"newest": "2026-08-31", "downloaded": 0, "errors": [],
                 "warnings": ["no orders recognised on the listing page; the site layout may have changed"]}}}))
    page = server.get("/")
    assert "Commission websites" in page and "2026-08-31" in page and "layout may have changed" in page


def test_unresolved_citation_gets_a_suggested_target(server):
    from regstudio import db, registry
    with db.session() as conn:
        reg = conn.execute("SELECT id, title FROM regulations").fetchone()
        clause = conn.execute("SELECT number FROM clauses WHERE regulation_id = ? AND number NOT LIKE '%(%' LIMIT 1",
                              (reg["id"],)).fetchone()["number"]
        cite = f"Regulation {clause} of the {reg['title']}"
        assert registry.suggest_target(conn, cite) == f"clause::{reg['id']}/{clause}"
        assert registry.suggest_target(conn, "Regulation 4 of some unrelated Grid Code") is None


def test_suggestion_understands_common_abbreviations(env):
    import sqlite3 as _s
    from regstudio import db, registry
    db.init()
    with db.session() as conn:
        conn.execute("INSERT INTO regulations(id, commission, title, status) VALUES (?, 'rerc', ?, 'proposed')",
                     ("rerc/geoa-2025", "RERC (Terms and Conditions for Green Energy Open Access) Regulations, 2025"))
        conn.execute("INSERT INTO clauses(id, regulation_id, number, text, status) VALUES (?, ?, '7', 'x', 'proposed')",
                     ("rerc/geoa-2025/7", "rerc/geoa-2025"))
        assert registry.suggest_target(conn, "Regulation 7 of the GEOA Regulations, 2025", "rerc") == "clause::rerc/geoa-2025/7"
        assert registry.suggest_target(conn, "Regulation 7 of the GEOA Regulations, 2025", "gerc") is None


def test_queue_flags_long_listing_titles(server):
    from regstudio import db
    with db.session() as conn:
        conn.execute("UPDATE documents SET title = ?, case_number = 'Petition No. 2416/2026' WHERE doc_type = 'order'",
                     ("M/s Sample Ltd: Petition filed under Section 142 of the Electricity Act 2003 for contravention of "
                      "directions in the Green Energy Open Access Regulations with respect to contract demand",))
    page = server.get("/")
    assert "Petition No. 2416/2026" in page and "needs a short title" in page


def test_preview_marks_drafts_and_never_touches_the_real_snapshot(server):
    out = publish.run(preview=True)
    prev = config.PREVIEW
    site = json.loads((prev / "site.json").read_text())
    orders = json.loads((prev / "orders.json").read_text())
    assert site["preview"] is True and orders and all(o["draft"] for o in orders)
    assert all(o["reviewed_by"] is None for o in orders)
    assert not list((prev / "pdf").iterdir())  # PDFs are linked, not copied, in a preview
    assert json.loads((config.SNAPSHOT / "orders.json").read_text() if (config.SNAPSHOT / "orders.json").exists() else "[]") == []
    import pytest as _p
    with _p.raises(ValueError):
        publish.run(preview=True, out=config.SNAPSHOT)
    assert out["orders"] == len(orders)


def _sample_draft():
    """A SAMPLE draft regulation dropped into the inbox the way the downloader would."""
    import hashlib
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800),
                        "SAMPLE - NOT A REAL ORDER OR REGULATION - FOR SOFTWARE TESTING ONLY\n"
                        "SAMPLE STATE ELECTRICITY REGULATORY COMMISSION\n"
                        "Draft Sample Green Energy Open Access (First Amendment) Regulations, 2026\n"
                        "The Commission proposes to amend Regulation 8 so that banking is settled monthly and "
                        "banking charges fall from eight to five percent of the energy banked.\n"
                        "Comments may be sent on or before 27.11.2026. A public hearing will be held on 03.12.2026.",
                        fontsize=11)
    data = doc.tobytes()
    folder = config.INBOX / "rerc" / "2026-11-12"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sample-draft.pdf").write_bytes(data)
    (folder / "sample-draft.json").write_text(json.dumps({
        "commission": "rerc", "doc_type": "draft", "source_url": "https://example.invalid/sample-draft.pdf",
        "downloaded_at": "2026-11-12T10:00:00+05:30", "sha256": hashlib.sha256(data).hexdigest(),
        "title": "Draft Sample Green Energy Open Access (First Amendment) Regulations, 2026",
        "doc_date": "2026-11-10", "related": [{"label": "Public Notice", "url": "https://example.invalid/pn.pdf"}]}))


def test_draft_regulation_is_summarised_reviewed_and_published(server):
    from regstudio import consult
    _sample_draft()
    intake.run(); extract.run()
    assert consult.run()["consultations"] == 1
    c = _db().execute("SELECT * FROM consultations").fetchone()
    assert c["summary_status"] == "proposed" and c["kind"] == "draft_amendment"
    assert c["comment_deadline"] == "2026-11-27" and c["hearing_date"] == "2026-12-03"  # read from the text
    assert publish.run()["consultations"] == 0  # nothing until a reviewer approves
    assert server(f"/consultation/{c['doc_id']}", {"action": "approve", "summary": "x"}) == 403
    server("/whoami", {"name": "Test Reviewer"})
    page = server.get(f"/consultation/{c['doc_id']}")
    assert "Approve for the website" in page and "Public Notice" in page
    assert "Draft regulations and consultations" in server.get("/")
    assert server(f"/consultation/{c['doc_id']}", {"action": "approve", "summary": "Proposal: monthly banking.",
                                                   "kind": "draft_amendment", "comment_deadline": "2026-11-28",
                                                   "proposes": "Banking monthly\nCharges 5%"}) == 303
    assert server(f"/consultation/{c['doc_id']}", {"action": "save", "comment_deadline": "28/11/2026"}) == 400
    assert publish.run()["consultations"] == 1
    pub = json.loads((config.SNAPSHOT / "consultations.json").read_text())[0]
    assert pub["comment_deadline"] == "2026-11-28" and pub["proposes"] == ["Banking monthly", "Charges 5%"]
    assert pub["reviewed_by"] == "Test Reviewer" and pub["sample"] is True and pub["related"][0]["label"] == "Public Notice"
    assert publish.run(clean=True)["consultations"] == 0


def test_impact_is_opt_in_cited_edited_and_published_with_the_summary(server):
    from regstudio import impact
    doc, _, _ = _ids()
    pids = [r[0] for r in _db().execute("SELECT pid FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (doc,))][:2]
    server("/whoami", {"name": "Test Reviewer"})
    page = server.get(f"/order/{doc}")
    assert "Request market impact assessment" in page
    assert impact.run()["impact"] == 0  # nothing requested, nothing assessed
    assert server(f"/impact/{doc}", {"action": "request"}) == 303
    assert _db().execute("SELECT impact FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0] == "requested"
    prepared = config.READER_OUTPUTS
    prepared.mkdir(parents=True, exist_ok=True)
    (prepared / f"{doc}.impact.json").write_text(json.dumps({
        "market_note": "Banking gets cheaper for C&I buyers.",
        "key_points": [{"text": "Banking charge falls", "basis": [pids[0]]}, {"text": "Invented point", "basis": ["p99.9"]}],
        "procurement": [], "open_questions": ["Procedure to follow"],
        "stakeholders": {"ci_consumers": {"effect": "opportunity", "comment": "lower banking cost", "basis": [pids[0]]},
                         "discoms": {"effect": "cost", "comment": "less banking income", "basis": ["p99.9"]}}}))
    import os
    os.environ["REGSTUDIO_READER"] = "file"; config.READER = "file"
    try:
        r = impact.run()
        assert r["impact"] == 1 and r["dropped_uncited"] == 2  # the uncited point and cell are dropped
    finally:
        os.environ["REGSTUDIO_READER"] = "mock"; config.READER = "mock"
    row = json.loads(_db().execute("SELECT impact FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0])
    assert list(row["stakeholders"]) == ["ci_consumers"] and row["key_points"] == [{"text": "Banking charge falls", "basis": [pids[0]]}]
    assert "level" not in row["stakeholders"]["ci_consumers"]
    assert "Market impact" in server.get(f"/order/{doc}")
    assert server(f"/impact/{doc}", {"action": "save", "market_note": "Edited.",
                                     "key_points": f"One [{pids[0]}]\nTwo [{pids[1]}]\nThree without citation",
                                     "effect_ci_consumers": "opportunity", "comment_ci_consumers": "x", "basis_ci_consumers": pids[1],
                                     "effect_storage": "cost", "comment_storage": "uncited"}) == 303
    assert publish.run()["orders"] == 0
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    publish.run()
    pub = json.loads((config.SNAPSHOT / "orders.json").read_text())[0]["impact"]
    assert pub["market_note"] == "Edited." and [k["text"] for k in pub["key_points"]] == ["One", "Two"]
    assert pub["stakeholders"] == {"ci_consumers": {"effect": "opportunity", "comment": "x", "basis": [pids[1]]}}
    # the overall rating is the reviewer's, never the model's
    assert json.loads((config.SNAPSHOT / "orders.json").read_text())[0]["rating"] is None
    assert server(f"/rating/{doc}", {"rating": "extreme"}) == 400
    assert server(f"/rating/{doc}", {"rating": "high"}) == 303
    publish.run()
    assert json.loads((config.SNAPSHOT / "orders.json").read_text())[0]["rating"] == "high"


def test_comment_drafts_are_requested_cited_reviewed_and_published(server):
    from regstudio import comments, consult
    _sample_draft()
    intake.run(); extract.run(); consult.run()
    draft = _db().execute("SELECT doc_id FROM consultations").fetchone()[0]
    pids = [r[0] for r in _db().execute("SELECT pid FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (draft,))][:2]
    server("/whoami", {"name": "Test Reviewer"})
    assert "Studio: draft comments" in server.get(f"/consultation/{draft}")
    assert server(f"/comments/{draft}", {"action": "request", "persona": "captive"}) == 303
    (config.READER_OUTPUTS).mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / f"{draft}.comment.captive.json").write_text(json.dumps({
        "position": "We support the draft with two changes.", "closing": "We request a hearing.",
        "points": [{"clause": "Regulation 4", "comment": "Monthly banking hurts seasonal users.", "suggestion": "Keep annual banking.", "basis": [pids[0]]},
                   {"clause": "Regulation 9", "comment": "Not in the text.", "suggestion": "x", "basis": ["p99.9"]}]}))
    import os
    os.environ["REGSTUDIO_READER"] = "file"; config.READER = "file"
    try:
        assert comments.run()["comments"] == 1
    finally:
        os.environ["REGSTUDIO_READER"] = "mock"; config.READER = "mock"
    row = _db().execute("SELECT body, status FROM comment_drafts WHERE doc_id = ? AND persona = 'captive'", (draft,)).fetchone()
    body = json.loads(row[0])
    assert row[1] == "proposed" and [p["clause"] for p in body["points"]] == ["Regulation 4"]  # the uncited point is dropped
    files = list(config.COMMENTS.rglob("captive.md"))
    assert files and "Keep annual banking." in files[0].read_text()
    server(f"/consultation/{draft}", {"action": "approve", "title": "Draft GEOA", "kind": "draft_regulation", "summary": "Proposal.",
                                      "proposes": "One", "comment_deadline": "", "hearing_date": "", "amends": ""})
    publish.run()
    pub = [c for c in json.loads((config.SNAPSHOT / "consultations.json").read_text()) if c["id"] == draft][0]
    assert pub["comments"] == {}  # a proposed comment draft is not published
    assert server(f"/comments/{draft}", {"action": "approve", "persona": "captive", "position": "Edited position.", "closing": "c",
                                         "clause_0": "Regulation 4", "comment_0": "Edited.", "suggestion_0": "s", "basis_0": pids[0]}) == 303
    publish.run()
    pub = [c for c in json.loads((config.SNAPSHOT / "consultations.json").read_text()) if c["id"] == draft][0]
    assert pub["comments"]["captive"]["position"] == "Edited position." and pub["comments"]["captive"]["draft"] is False


def test_figures_keep_only_sound_cited_charts_and_publish_with_the_summary(server):
    from regstudio import figures
    doc, _, _ = _ids()
    pids = [r[0] for r in _db().execute("SELECT pid FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (doc,))][:2]
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / f"{doc}.figures.json").write_text(json.dumps({"charts": [
        {"type": "bars", "title": "Banking charge", "unit": "%", "items": [
            {"label": "Before", "value": 8, "basis": [pids[0]], "context": True}, {"label": "After", "value": 5, "basis": [pids[1]]},
            {"label": "Invented", "value": 3, "basis": ["p99.9"]}]},
        {"type": "bars", "title": "One number is not a chart", "unit": "MW", "items": [
            {"label": "Only", "value": 5, "basis": [pids[0]]}, {"label": "Uncited", "value": 7, "basis": ["p99.9"]}]},
        {"type": "timeline", "title": "Dates", "items": [
            {"label": "Order", "start": "2026-11-04", "basis": [pids[0]]}, {"label": "Bad", "start": "2026-13-40", "basis": [pids[0]]},
            {"label": "Period", "start": "2026-11-01", "end": "2027-03-31", "basis": [pids[1]]}]}]}))
    import os
    os.environ["REGSTUDIO_READER"] = "file"; config.READER = "file"
    try:
        r = figures.run()
        assert r["figures"] == 1 and r["charts"] == 2  # the one-number chart is dropped
    finally:
        os.environ["REGSTUDIO_READER"] = "mock"; config.READER = "mock"
    charts = json.loads(_db().execute("SELECT figures FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0])
    assert [c["type"] for c in charts] == ["bars", "timeline"]
    assert [i["label"] for i in charts[0]["items"]] == ["Before", "After"] and [i["label"] for i in charts[1]["items"]] == ["Order", "Period"]
    server("/whoami", {"name": "Test Reviewer"})
    assert "Charts in the summary" in server.get(f"/order/{doc}")
    assert server(f"/figures/{doc}", {"action": "save", "figures_json": json.dumps(charts), "drop_1": "on"}) == 303
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    publish.run()
    pub = json.loads((config.SNAPSHOT / "orders.json").read_text())[0]["figures"]
    assert len(pub) == 1 and pub[0]["title"] == "Banking charge" and pub[0]["unit"] == "%"


def test_summary_is_checked_by_numbers_and_two_reviewers_before_legal_review(server):
    from regstudio import checks
    doc, _, _ = _ids()
    c = _db()
    pid = c.execute("SELECT pid FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (doc,)).fetchone()[0]
    c.execute("UPDATE orders SET summary = summary || ' The charge is Rs 987.65 per unit.' WHERE doc_id = ?", (doc,)); c.commit()
    assert checks.numbers_check("Tariff of Rs 16.62 on 04.11.2026 for 1,200 MW", "tariff 116.625; dated 4th November, 2026; 1200 MW") == {"checked": 3, "missing": ["16.62"]}
    assert checks.numbers_check("ceiling of Rs 4.59", "fixed at Rs.4.59/kWh")["missing"] == []
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / f"{doc}.check.fact.json").write_text(json.dumps({"own_reading": "r", "verdict": "pass", "issues": [
        {"claim": "Rs 987.65", "problem": "Not in the order.", "severity": "material", "basis": [pid, "p99.9"]}]}))
    (config.READER_OUTPUTS / f"{doc}.check.legal.json").write_text(json.dumps({"own_reading": "r", "verdict": "pass", "issues": []}))
    import os
    os.environ["REGSTUDIO_READER"] = "file"; config.READER = "file"
    try:
        r = checks.run()
        assert r["needs_attention"] >= 1
    finally:
        os.environ["REGSTUDIO_READER"] = "mock"; config.READER = "mock"
    got = json.loads(_db().execute("SELECT checks FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0])
    assert "987.65" in got["numbers"]["missing"] and got["status"] == "attention"
    assert got["fact"]["verdict"] == "concerns" and got["fact"]["issues"][0]["basis"] == [pid]  # a reviewer with findings has not passed; invented citation dropped
    assert got["legal"]["verdict"] == "pass"
    server("/whoami", {"name": "Test Reviewer"})
    page = server.get(f"/order/{doc}")
    assert "Pre-review checks" in page and "needs attention" in page and "Not in the order." in page
    assert _db().execute("SELECT summary_status FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0] == "proposed"  # checks never approve
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    publish.run()
    pub = json.loads((config.SNAPSHOT / "orders.json").read_text())[0]
    assert pub["checked"] == {"reviewers": 2, "numbers": True} and "Not in the order" not in json.dumps(pub)
    assert server(f"/checks/{doc}", {"action": "redo"}) == 303
    assert _db().execute("SELECT checks FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0] is None


def test_flow_schematic_keeps_only_cited_steps():
    from regstudio import figures
    out = figures.clean({"charts": [{"type": "flow", "title": "Who gets the waiver", "items": [
        {"label": "Commissioned by June 2028", "detail": "100% waiver", "otherwise": "Tapered waiver", "basis": ["p1.1"]},
        {"label": "Invented step", "basis": ["p9.9"]}, {"label": "Result", "detail": "No ISTS charges", "basis": ["p1.2"]}]}]}, {"p1.1", "p1.2"})
    assert out[0]["type"] == "flow" and [i["label"] for i in out[0]["items"]] == ["Commissioned by June 2028", "Result"]
    assert out[0]["items"][0]["otherwise"] == "Tapered waiver" and "unit" not in out[0]


def test_digest_edition_keeps_only_cited_points_and_publishes_with_approved_items(server):
    import datetime as dt
    import os
    from regstudio import drafting
    doc, _, _ = _ids()
    c = _db()
    pids = [r[0] for r in c.execute("SELECT pid FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (doc,))]
    text = " ".join(r[0] for r in c.execute("SELECT text FROM paragraphs WHERE doc_id = ?", (doc,)))
    import re
    figure = re.search(r"\d[\d,]*\.?\d*", text).group(0)
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / "2026-W47.digest.json").write_text(json.dumps({
        "intro": "Lead for the edition.", "order": [doc[:10], "deadbeef00"],
        "key_points": [{"text": "Cited point.", "basis": [{"doc": doc[:10], "pid": pids[0]}]},
                       {"text": "Invented paragraph.", "basis": [{"doc": doc[:10], "pid": "p99.9"}]},
                       {"text": "Unknown document.", "basis": [{"doc": "deadbeef00", "pid": "p1.1"}]}],
        "numbers": [{"value": figure, "label": "A figure in the order", "doc": doc, "pid": pids[0]},
                    {"value": "987.65 MW", "label": "Not in the order", "doc": doc, "pid": pids[0]}],
        "charts": [{"type": "bars", "title": "Across orders", "unit": "MW", "items": [
            {"label": "A", "value": 1, "doc": doc, "basis": [pids[0]]}, {"label": "B", "value": 2, "doc": doc, "basis": [pids[1]]},
            {"label": "C", "value": 3, "doc": doc, "basis": ["p77.1"]}]}],
        "watch": [{"date": "2026-11-17", "text": "Hearing", "doc": doc, "pid": pids[0]}]}))
    os.environ["REGSTUDIO_READER"] = "file"; config.READER = "file"
    try:
        out = drafting.run(day=dt.date(2026, 11, 20))
    finally:
        os.environ["REGSTUDIO_READER"] = "mock"; config.READER = "mock"
    assert out["digest"] == "2026-W47" and out["edition"] == "2026-11-20"
    assert out["key_points"] == 1 and out["numbers"] == 1 and out["charts"] == 1 and out["watch"] == 1
    g = _db().execute("SELECT * FROM digests WHERE id = '2026-W47'").fetchone()
    assert json.loads(g["items"]) == [doc] and g["status"] == "proposed"
    assert [i["label"] for i in json.loads(g["charts"])[0]["items"]] == ["A", "B"]
    server("/whoami", {"name": "Test Reviewer"})
    page = server.get("/digest/2026-W47")
    assert "Cited point." in page and "Invented paragraph." not in page and "Numbers to know" in page
    publish.run(preview=True)
    pre = json.loads((config.PREVIEW / "digests.json").read_text())
    assert pre[0]["draft"] and pre[0]["key_points"][0]["basis"][0]["href"].startswith("/orders/")
    assert server("/digest/2026-W47", {"intro": "Reviewed lead.", "action": "approve"}) == 303
    publish.run()
    assert json.loads((config.SNAPSHOT / "digests.json").read_text()) == []   # the item's own summary is not approved yet
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    publish.run()
    d = json.loads((config.SNAPSHOT / "digests.json").read_text())[0]
    assert d["intro"] == "Reviewed lead." and d["numbers"][0]["value"] == figure and d["watch"][0]["date"] == "2026-11-17"
    assert not d["draft"]


def test_prepared_files_are_used_in_claude_mode_and_headlines_fill_older_summaries(server, monkeypatch):
    from regstudio import claude_runner, headlines
    doc, _, _ = _ids()
    called = []
    monkeypatch.setattr(claude_runner, "ask_json", lambda *a, **k: called.append(1) or {"headline": "From Claude"})
    monkeypatch.setattr(headlines, "ask_json", lambda *a, **k: called.append(1) or {"headline": "From Claude"})
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / f"{doc}.headline.json").write_text(json.dumps({"headline": "Prepared headline for this order"}))
    monkeypatch.setattr(config, "READER", "claude")
    assert headlines.run() == {"headlines": 1, "failed": 0}
    assert not called                                      # the prepared file was used, Claude was not asked
    assert _db().execute("SELECT headline FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0] == "Prepared headline for this order"
    (config.READER_OUTPUTS / f"{doc}.headline.json").write_text(json.dumps({"headline": "x"}))   # too short: fails that document only
    c = _db(); c.execute("UPDATE orders SET headline = NULL"); c.commit()
    assert headlines.run()["failed"] == 1
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/order/{doc}/summary", {"action": "save", "summary": "S", "issue": "i", "outcome": "o", "headline": "Reviewer's headline"})
    publish.run(preview=True)
    assert json.loads((config.PREVIEW / "orders.json").read_text())[0]["headline"] == "Reviewer's headline"


# ---------- comments, revisions, memory, commercial illustrations ----------

def _first_pid(doc):
    return _db().execute("SELECT pid FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (doc,)).fetchone()[0]


def test_comment_revision_and_lessons(server, monkeypatch):
    from regstudio import config as _cfg
    monkeypatch.setattr(_cfg, 'READER', 'file')
    from regstudio import config, learning
    doc, _, _ = _ids()
    pid = _first_pid(doc)
    server("/whoami", {"name": "Test Reviewer"})
    assert server(f"/notes/{doc}", {"target": "summary", "body": "Say that the holding is limited to existing plants.",
                                    "quote": "all plants"}) == 303
    cid = _db().execute("SELECT id FROM review_comments WHERE doc_id = ?", (doc,)).fetchone()[0]
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / f"{doc}.revise.json").write_text(json.dumps({
        "replies": [{"comment_id": cid, "reply": "Narrowed to existing plants.", "action": "changed"}],
        "summary": "The holding applies only to existing plants.", "basis": [pid],
        "lessons": [{"kind": "style", "text": "State who a holding applies to.", "scope": "all"},
                    {"kind": "fact", "text": "A fact with no paragraph is not kept.", "scope": "all"}]}))
    assert learning.revise() == {"revised": 1, "failed": 0}
    c = _db()
    assert c.execute("SELECT status, reply FROM review_comments WHERE id = ?", (cid,)).fetchone()["status"] == "answered"
    rev = c.execute("SELECT id, fields FROM revisions WHERE doc_id = ?", (doc,)).fetchone()
    assert json.loads(rev["fields"]) == {"summary": "The holding applies only to existing plants."}
    lessons = c.execute("SELECT id, kind, status FROM lessons").fetchall()
    assert [l["kind"] for l in lessons] == ["style"] and lessons[0]["status"] == "proposed"
    page = server.get(f"/order/{doc}")
    assert "Proposed revision" in page and "Narrowed to existing plants." in page and "State who a holding applies to." in page
    # Nothing in prompts until a reviewer approves the lesson.
    assert "State who" not in learning.with_notes("prompt")
    assert server(f"/lesson/{lessons[0]['id']}", {"action": "approve"}) == 303
    assert "State who a holding applies to." in learning.with_notes("prompt")
    assert "State who a holding applies to." in (config.MEMORY / "house_notes.md").read_text()
    # Accepting changes the text but does not approve it.
    assert server(f"/revision/{rev['id']}", {"action": "accept"}) == 303
    o = _db().execute("SELECT summary, summary_status FROM orders WHERE doc_id = ?", (doc,)).fetchone()
    assert o["summary"] == "The holding applies only to existing plants." and o["summary_status"] == "proposed"
    assert _db().execute("SELECT status FROM review_comments WHERE id = ?", (cid,)).fetchone()[0] == "resolved"
    assert server(f"/revision/{rev['id']}", {"action": "accept"}) == 409


def test_rejected_revision_reopens_comments(server, monkeypatch):
    from regstudio import config as _cfg
    monkeypatch.setattr(_cfg, 'READER', 'file')
    from regstudio import learning
    doc, _, _ = _ids()
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/notes/{doc}", {"target": "headline", "body": "Shorter headline please."})
    with db_session() as conn:
        conn.execute("UPDATE orders SET headline = 'Old headline' WHERE doc_id = ?", (doc,))
    from regstudio import config
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    cid = _db().execute("SELECT id FROM review_comments").fetchone()[0]
    (config.READER_OUTPUTS / f"{doc}.revise.json").write_text(json.dumps(
        {"replies": [{"comment_id": cid, "reply": "Shortened.", "action": "changed"}], "headline": "New headline"}))
    learning.revise(doc=doc)
    rid = _db().execute("SELECT id FROM revisions").fetchone()[0]
    assert server(f"/revision/{rid}", {"action": "reject"}) == 303
    assert _db().execute("SELECT status FROM review_comments WHERE id = ?", (cid,)).fetchone()[0] == "open"
    assert _db().execute("SELECT headline FROM orders WHERE doc_id = ?", (doc,)).fetchone()[0] == "Old headline"


def db_session():
    from regstudio import db
    return db.session()


def test_commercial_arithmetic_is_done_by_code():
    from regstudio import commercial
    out = {"title": "t", "question": "q",
           "inputs": [{"id": "mw", "label": "Capacity", "value": 100, "unit": "MW", "basis": ["p1.1"]},
                      {"id": "rate", "label": "Rate", "value": 6.27, "unit": "Rs/kWh", "basis": ["p1.2"]},
                      {"id": "hours", "label": "Hours", "value": 4, "assumption": "four hours a day"}],
           "steps": [{"id": "mwh", "label": "Energy", "expr": "mw * hours * 365", "unit": "MWh"},
                     {"id": "crore", "label": "Cost", "expr": "mwh * rate / 10000", "unit": "Rs crore", "decimals": 2}],
           "takeaway": "About Rs {crore} crore a year."}
    r = commercial.build(out, {"p1.1", "p1.2"})
    assert r["steps"][0]["shown"] == "1,46,000" and r["takeaway"] == "About Rs 91.54 crore a year."
    assert commercial.build({**out, "takeaway": "About Rs 92 crore."}, {"p1.1", "p1.2"}) is None      # digits typed by the model
    assert commercial.build(out, {"p1.1"}) is None                                                   # input neither cited nor assumed
    bad = {**out, "steps": [{"id": "x", "label": "x", "expr": "__import__('os')"}]}
    assert commercial.build(bad, {"p1.1", "p1.2"}) is None
    assert commercial.fmt(12345678.9, 1) == "1,23,45,678.9"


def test_commercial_needs_commercial_team_approval_to_publish(server, monkeypatch):
    from regstudio import config as _cfg
    monkeypatch.setattr(_cfg, 'READER', 'file')
    from regstudio import commercial, config, publish
    doc, _, _ = _ids()
    pid = _first_pid(doc)
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    assert server(f"/commercial/{doc}", {"action": "request"}) == 303
    config.READER_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (config.READER_OUTPUTS / f"{doc}.commercial.json").write_text(json.dumps({
        "title": "Illustration", "question": "What does it cost?",
        "inputs": [{"id": "a", "label": "A", "value": 2, "basis": [pid]}, {"id": "b", "label": "B", "value": 3, "assumption": "for the example"}],
        "steps": [{"id": "c", "label": "Product", "expr": "a * b"}], "takeaway": "The product is {c}."}))
    assert commercial.run()["illustrations"] == 1
    assert "The product is 6." in server.get(f"/order/{doc}")

    def published():
        publish.run()
        return json.loads((config.SNAPSHOT / "orders.json").read_text())[0].get("commercial")
    assert published() is None
    assert server(f"/commercial/{doc}", {"action": "approve"}) == 303
    c = published()
    assert c["takeaway"] == "The product is 6." and c["approved_by"] == "Test Reviewer" and c["draft"] is False


def test_memory_page_and_manual_notes(server):
    from regstudio import learning
    server("/whoami", {"name": "Test Reviewer"})
    assert server("/memory", {"kind": "fact", "text": "No source given.", "scope": "all"}) == 400
    assert server("/memory", {"kind": "style", "text": "Use Rs, not INR.", "scope": "all"}) == 303
    assert "Use Rs, not INR." in server.get("/memory")
    assert "Use Rs, not INR." in learning.with_notes("Summarise this order.")


def test_review_priority_puts_open_drafts_and_multi_party_orders_first(server):
    import datetime as dt
    from regstudio import priority
    today = dt.date(2026, 11, 14)
    draft = priority.score({"kind": "draft", "commission": "kerc", "title": "Draft Procurement of Energy from Renewable Sources Regulations",
                            "summary": "Proposes open access and banking changes.", "comment_deadline": "2026-11-20"}, today)
    closed = priority.score({"kind": "draft", "commission": "kerc", "title": "Draft Supply Code amendment", "comment_deadline": "2026-10-01"}, today)
    parties = json.dumps([{"name": n, "role": "respondent"} for n in ("Acme Solar Ltd", "Beta Wind Ltd", "State Discom Ltd", "State Load Despatch Centre")])
    multi = priority.score({"kind": "order", "commission": "cerc", "title": "Bank guarantee encashment under a storage tender",
                            "significance": 4, "parties": parties, "doc_date": "2026-11-10"}, today)
    routine = priority.score({"kind": "order", "commission": "cerc", "title": "Extension of time", "significance": 1,
                              "parties": json.dumps([{"name": "One Petitioner Ltd"}]), "doc_date": "2026-09-01"}, today)
    assert draft["score"] > multi["score"] > routine["score"] and draft["score"] > closed["score"]
    assert draft["band"] == "Review first" and routine["band"] == "When time allows"
    assert multi["leads"] == ["Acme Solar Ltd", "Beta Wind Ltd", "State Discom Ltd"]          # the load despatch centre is not a lead
    assert all(0 <= v <= priority.MAX[k] for k, v in draft["parts"].items()) and draft["score"] <= 100
    page = server.get("/")
    assert "Review these first" in page and "Priority" in page
    doc, _, _ = _ids()
    assert "Review priority" in server.get(f"/order/{doc}")
    from regstudio import config, publish
    server("/whoami", {"name": "Test Reviewer"})
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    publish.run()
    assert "priority" not in json.loads((config.SNAPSHOT / "orders.json").read_text())[0]      # internal only
