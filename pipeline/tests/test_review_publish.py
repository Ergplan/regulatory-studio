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
