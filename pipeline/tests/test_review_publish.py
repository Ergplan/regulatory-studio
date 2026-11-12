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
