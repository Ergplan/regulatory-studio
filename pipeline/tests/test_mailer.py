import base64
import email
import json
import sqlite3

import pytest

from regstudio import config


@pytest.fixture()
def outbox(env, monkeypatch):
    monkeypatch.setenv("REGSTUDIO_MAIL", "outbox")
    from regstudio import mailer
    return mailer


def _mails(mailer):
    return {p.name: email.message_from_bytes(p.read_bytes()) for p in sorted(mailer.OUTBOX.glob("*.eml"))}


def _body(m):
    return next(p.get_payload(decode=True).decode() for p in m.walk() if p.get_content_type() == "text/plain")


def test_headers_cannot_be_injected_and_bad_addresses_are_refused(outbox):
    m = outbox.build(["sales@joulewise.com"], "Hello\r\nBcc: evil@example.com", "x", reply_to="a@b.com")
    assert "\n" not in m["Subject"] and m["Bcc"] is None
    assert m["From"] == "jouleWise Regulatory Studio <mahak.mittal@joulewise.com>"
    for bad in ("a@b.com\r\nBcc: x@y.com", "not an address", "a@b.com, c@d.com"):
        with pytest.raises(outbox.MailError):
            outbox.build([bad], "s", "t")


def test_each_message_is_sent_once_and_logged(outbox):
    assert outbox.send("test", "1", ["sales@joulewise.com"], "Subject", "Body") == "written"
    assert outbox.send("test", "1", ["sales@joulewise.com"], "Subject", "Body") == "already"
    assert len(_mails(outbox)) == 1
    row = sqlite3.connect(config.DB_PATH).execute("SELECT status, to_addr FROM mail_log WHERE kind = 'test'").fetchone()
    assert row == ("written", "sales@joulewise.com")


def test_project_requests_and_chat_contacts_are_mailed_to_sales(outbox, monkeypatch):
    from regstudio import mirror
    calls = []
    lead = {"id": 7, "at": "2026-11-26T06:00:00Z", "name": "Asha Rao", "email": "asha@example.com", "org": "Rao Textiles",
            "business": "Industry", "state": "Gujarat", "asked": "Open access savings", "reading": "GERC green energy order",
            "page": "/orders/abc", "message": "Can you look at our 2 MW plan?"}
    chat = {"id": "a" * 32, "started_at": "2026-11-26T05:00:00Z", "page": "/", "name": "Vikram", "company": "VK Steel",
            "reach": "vikram@example.com", "messages": [{"at": 1, "text": "Do you cover MERC?"}]}

    def fake(op, **body):
        calls.append((op, body))
        return {"leads": [lead], "chats": [chat]} if op == "leads" else {"ok": True}
    monkeypatch.setattr(mirror, "call", fake)
    assert outbox.relay() == {"mailed": 2}
    assert ("leads_mailed", {"leads": [7], "chats": ["a" * 32]}) in calls
    mails = list(_mails(outbox).values())
    assert {m["To"] for m in mails} == {"sales@joulewise.com"}
    by_reply = {m["Reply-To"]: m for m in mails}
    assert "Can you look at our 2 MW plan?" in _body(by_reply["asha@example.com"])
    assert "Do you cover MERC?" in _body(by_reply["vikram@example.com"])
    assert "Asha Rao" in by_reply["asha@example.com"]["Subject"]
    assert outbox.relay() == {"mailed": 2} and len(_mails(outbox)) == 2      # acknowledged again, never sent twice


def test_chat_with_a_phone_number_has_no_reply_to(outbox):
    m = outbox.chat_mail({"id": "b" * 32, "name": "R", "reach": "+91 98100 00000", "messages": []})
    assert m["reply_to"] is None and "+91 98100 00000" in m["text"]


def test_invitations_asked_for_on_the_admin_page_are_made_here_and_emailed(outbox, monkeypatch):
    from regstudio import mirror
    calls = []

    def fake(op, **body):
        calls.append((op, body))
        if op == "invite_requests":
            return {"requests": [{"id": 3, "name": "Neha Gupta", "email": "neha@urjapraxis.com", "team": "urja"}]}
        return {"ok": True}
    monkeypatch.setattr(mirror, "call", fake)
    assert mirror.invite_requests() == 1
    made = next(b for op, b in calls if op == "invite")
    assert made["email"] == "neha@urjapraxis.com" and len(made["token_hash"]) == 64   # the site only gets the hash
    assert ("invite_requests_done", {"results": [{"id": 3, "status": "emailed", "note": ""}]}) in calls
    (m,) = _mails(outbox).values()
    assert m["To"] == "neha@urjapraxis.com"
    body = _body(m)
    link = next(w for w in body.split() if "/_/invite/" in w)
    import hashlib
    assert hashlib.sha256(link.rsplit("/", 1)[1].encode()).hexdigest() == made["token_hash"]


def test_review_notice_lists_what_waits_highest_priority_first(outbox):
    from regstudio import drafting, extract, intake, reader, registry, triage
    assert outbox.review_notice(["lawyer@urjapraxis.com"]) == "nothing waiting"
    intake.run(); extract.run(); registry.run(); triage.run(); reader.run(); drafting.run()
    assert outbox.review_notice([]) .startswith("no addresses")
    assert outbox.review_notice(["lawyer@urjapraxis.com"]) == "written"
    (m,) = _mails(outbox).values()
    assert "waiting for review" in m["Subject"] and "/urja-praxis" in _body(m)
    assert outbox.review_notice(["lawyer@urjapraxis.com"]) == "already"        # once a day


def test_gmail_mode_needs_setup_and_sends_through_the_api(env, monkeypatch):
    monkeypatch.setenv("REGSTUDIO_MAIL", "gmail")
    from regstudio import mailer
    with pytest.raises(mailer.NotSetUp):
        mailer.send("test", "x", ["sales@joulewise.com"], "s", "t")
    sent = {}

    class Resp:
        status_code = 200
        def json(self):
            return {"id": "gm-1"}

    class Session:
        def post(self, url, json, timeout):
            sent["url"], sent["raw"] = url, json["raw"]
            return Resp()
    monkeypatch.setattr(mailer, "_session", lambda: Session())
    assert mailer.send("test", "y", ["sales@joulewise.com"], "Subject", "Body") == "sent"
    assert sent["url"].endswith("/users/me/messages/send")
    m = email.message_from_bytes(base64.urlsafe_b64decode(sent["raw"]))
    assert m["To"] == "sales@joulewise.com" and _body(m).strip() == "Body"


def test_setup_accepts_only_a_desktop_client(env, tmp_path):
    from regstudio import mailer
    web = tmp_path / "web.json"
    web.write_text(json.dumps({"web": {"client_id": "x"}}))
    with pytest.raises(mailer.MailError, match="Desktop"):
        mailer.setup(str(web))
    with pytest.raises(mailer.MailError, match="no file"):
        mailer.setup(str(tmp_path / "missing.json"))
