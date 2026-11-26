"""Senior reviewer precedence: Kartik decides on his own; Shikha can change anything; Kartik cannot change Shikha's."""

import json
import urllib.error
import urllib.parse
import urllib.request

from regstudio import config, publish
from test_review_publish import _db, _ids, server  # noqa: F401  (fixture)

KARTIK = ("Kartik", "kartik@urjapraxis.com")
SHIKHA = ("Shikha Ohri", "shikha@urjapraxis.com")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def act(server, path, data, who):
    """A form as the sync job replays it from the review site: the reviewer's name and verified email."""
    from regstudio import mirror
    req = urllib.request.Request(server.url + path, data=urllib.parse.urlencode(data, doseq=True).encode(), headers={
        "X-Studio-Mirror": mirror.local_token(), "X-Studio-Reviewer": urllib.parse.quote(who[0]),
        "X-Studio-Reviewer-Email": urllib.parse.quote(who[1]), "Content-Type": "application/x-www-form-urlencoded"})
    try:
        r = urllib.request.build_opener(NoRedirect).open(req)
        return r.status, r.headers.get("location"), ""
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, e.headers.get("location"), (json.loads(body).get("detail", "") if body.startswith("{") else body)


def _order(doc):
    return _db().execute("SELECT summary_status, reviewer, summary FROM orders WHERE doc_id = ?", (doc,)).fetchone()


def _public():
    publish.run()
    return {o["id"]: o for o in json.loads((config.SNAPSHOT / "orders.json").read_text())}


APPROVE = lambda text: {"action": "approve", "summary": text, "issue": "i", "outcome": "o"}   # noqa: E731


def test_kartik_approves_alone_and_shikha_overrides(server):
    doc, _, _ = _ids()
    code, where, _ = act(server, f"/order/{doc}/summary", APPROVE("Kartik's text."), KARTIK)
    assert code == 303 and where == f"/order/{doc}"
    assert tuple(_order(doc)) == ("approved", "Kartik", "Kartik's text.")
    assert _public()[doc]["reviewed_by"] == "Kartik"                       # no second approval needed

    code, where, _ = act(server, f"/order/{doc}/summary", {"action": "reject"}, SHIKHA)
    assert code == 303 and where == f"/order/{doc}"                         # stays on the item
    assert _order(doc)["summary_status"] == "rejected" and doc not in _public()
    rows = _db().execute("SELECT * FROM review_decisions WHERE kind = 'order' AND object = ? ORDER BY id", (doc,)).fetchall()
    assert [(r["reviewer"], r["rank"], r["action"]) for r in rows] == [("Kartik", 1, "approve"), ("Shikha Ohri", 2, "reject")]
    assert rows[1]["overrides"] == rows[0]["id"] and rows[1]["status_before"] == "approved"
    assert json.loads(rows[1]["text_before"])["summary"] == "Kartik's text."   # what Kartik approved is kept


def test_kartik_cannot_change_shikhas_decision_but_can_comment(server):
    doc, _, _ = _ids()
    act(server, f"/order/{doc}/summary", APPROVE("Kartik's text."), KARTIK)
    act(server, f"/order/{doc}/summary", APPROVE("Shikha's text."), SHIKHA)
    for data in (APPROVE("Kartik again."), {"action": "save", "summary": "edit", "issue": "", "outcome": ""}, {"action": "reject"}):
        code, _, detail = act(server, f"/order/{doc}/summary", data, KARTIK)
        assert code == 409 and "Shikha Ohri (senior reviewer) approved this" in detail
    assert tuple(_order(doc)) == ("approved", "Shikha Ohri", "Shikha's text.")
    assert _public()[doc]["reviewed_by"] == "Shikha Ohri"
    refused = _db().execute("SELECT count(*) FROM review_decisions WHERE object = ? AND refused = 1", (doc,)).fetchone()[0]
    assert refused == 3                                                    # attempts are on record
    assert act(server, f"/notes/{doc}", {"body": "I think para 4 says more.", "target": "summary"}, KARTIK)[0] == 303
    # Shikha can still change her own decision
    assert act(server, f"/order/{doc}/summary", {"action": "reject"}, SHIKHA)[0] == 303
    assert _order(doc)["summary_status"] == "rejected"
    # and Kartik's late approval from an old page cannot bring it back
    assert act(server, f"/order/{doc}/summary", APPROVE("stale"), KARTIK)[0] == 409 and doc not in _public()


def test_seniority_comes_from_the_verified_email_not_the_name(server):
    doc, _, _ = _ids()
    act(server, f"/order/{doc}/summary", {"action": "reject"}, SHIKHA)
    assert act(server, f"/order/{doc}/summary", APPROVE("x"), ("Shikha Ohri", "someone@example.com"))[0] == 409
    server("/whoami", {"name": "Shikha Ohri"})                               # a typed name on the local screen
    assert server(f"/order/{doc}/summary", APPROVE("x")) == 409
    assert _order(doc)["summary_status"] == "rejected"


def test_pages_show_the_final_decision_and_the_record(server):
    doc, _, _ = _ids()
    act(server, f"/order/{doc}/summary", APPROVE("Kartik's text."), KARTIK)
    act(server, f"/order/{doc}/summary", APPROVE("Shikha's text."), SHIKHA)
    act(server, f"/order/{doc}/summary", APPROVE("again"), KARTIK)
    server("/whoami", {"name": "Reader"})
    page = server.get(f"/order/{doc}")
    assert "Final decision by Shikha Ohri" in page and "Decision record" in page
    assert "overrode Kartik&#39;s approved decision" in page and "refused" in page
    assert "final · Shikha Ohri" in server.get("/urja-praxis")


def test_other_decisions_follow_the_same_rule(server):
    doc, _, links = _ids()
    lid = links[0]["id"]
    act(server, f"/link/{lid}", {"action": "reject"}, SHIKHA)
    assert act(server, f"/link/{lid}", {"action": "reopen"}, KARTIK)[0] == 409
    act(server, "/memory", {"kind": "style", "text": "Say 'the Commission', not 'the Hon'ble Commission'."}, KARTIK)
    lesson = _db().execute("SELECT id FROM lessons ORDER BY id DESC").fetchone()[0]
    act(server, f"/lesson/{lesson}", {"action": "retire"}, SHIKHA)
    assert act(server, f"/lesson/{lesson}", {"action": "approve"}, KARTIK)[0] == 409
    assert _db().execute("SELECT status FROM lessons WHERE id = ?", (lesson,)).fetchone()[0] == "retired"
    week = _db().execute("SELECT id FROM digests").fetchone()[0]
    act(server, f"/digest/{week}", {"intro": "Shikha's lead.", "action": "approve"}, SHIKHA)
    assert act(server, f"/digest/{week}", {"intro": "Kartik's lead.", "action": "save"}, KARTIK)[0] == 409
    assert _db().execute("SELECT intro FROM digests WHERE id = ?", (week,)).fetchone()[0] == "Shikha's lead."


def test_kartiks_own_decisions_stay_his_to_change(server):
    doc, _, _ = _ids()
    act(server, f"/order/{doc}/summary", {"action": "reject"}, KARTIK)
    assert act(server, f"/order/{doc}/summary", APPROVE("Changed my mind."), KARTIK)[0] == 303
    assert _order(doc)["summary_status"] == "approved"
