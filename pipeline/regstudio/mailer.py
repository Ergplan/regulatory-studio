"""Mail sent by the studio Mac through the Gmail API, as the jouleWise work account (default
mahak.mittal@joulewise.com), with the gmail.send scope only: it can send, never read the mailbox.

Set up once on the Mac:  regstudio mail-setup --client ~/Downloads/credentials.json
That copies the Desktop OAuth client into data/store/gmail_client.json, opens the browser for the
account owner to sign in and allow sending, and keeps the refresh token in data/store/gmail_token.json.
Both files stay on the Mac (data/store is never committed) and are readable by this user only.

What is mailed:
- project requests and chat contact details from the public site, to SALES (sales@joulewise.com),
  with Reply-To set to the visitor's address (`relay`, run by the sync job);
- reviewer invitations, to the invited reviewer (`regstudio invite`);
- a "waiting for review" note, to the addresses in REVIEW_NOTIFY (`regstudio mail-review`).

Every message is recorded in the mail_log table under a (kind, ref) key and is never sent twice.
With REGSTUDIO_MAIL=outbox (tests, rehearsals) messages are written to data/store/mail_outbox/*.eml instead.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import shutil
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from . import config, db

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CLIENT = config.STORE / "gmail_client.json"
TOKEN = config.STORE / "gmail_token.json"
OUTBOX = Path(os.environ.get("REGSTUDIO_MAIL_OUTBOX", config.STORE / "mail_outbox"))
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

FROM = os.environ.get("REGSTUDIO_MAIL_FROM", "mahak.mittal@joulewise.com")
FROM_NAME = os.environ.get("REGSTUDIO_MAIL_FROM_NAME", "jouleWise Regulatory Studio")
SALES = os.environ.get("REGSTUDIO_MAIL_SALES", "sales@joulewise.com")
REVIEW_NOTIFY = [a.strip() for a in os.environ.get("REGSTUDIO_MAIL_REVIEW", "").split(",") if a.strip()]

EMAIL = re.compile(r"^[^\s@<>,;\"]+@[^\s@<>,;\"]+\.[^\s@<>,;\"]{2,}$")


class MailError(Exception):
    pass


class NotSetUp(MailError):
    pass


def mode() -> str:
    return os.environ.get("REGSTUDIO_MAIL", "gmail")


def ready() -> bool:
    return mode() == "outbox" or TOKEN.exists()


def _line(s: str, n: int = 200) -> str:
    """One header line: no CR/LF (header injection) and no control characters."""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(s or "")).strip()[:n]


def _addr(a: str) -> str:
    a = _line(a, 200).lower()
    if not EMAIL.match(a):
        raise MailError(f"not an email address: {a!r}")
    return a


# ---- one-time setup -------------------------------------------------------------------------------------------

def setup(client_path: str | None = None, port: int = 0) -> str:
    """Runs Google's sign-in in this Mac's browser and stores the refresh token. Returns the token path."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise MailError("missing package: run  pip install -e pipeline  again") from e
    config.STORE.mkdir(parents=True, exist_ok=True)
    if client_path:
        src = Path(client_path).expanduser()
        if not src.exists():
            raise MailError(f"no file at {src}")
        try:
            kind = next(iter(json.loads(src.read_text())))
        except (ValueError, StopIteration) as e:
            raise MailError(f"{src} is not an OAuth client file from Google Cloud") from e
        if kind != "installed":
            raise MailError(f"{src} is a '{kind}' client; download the Desktop app client instead")
        shutil.copyfile(src, CLIENT)
        os.chmod(CLIENT, 0o600)
    if not CLIENT.exists():
        raise MailError("no OAuth client yet: run  regstudio mail-setup --client ~/Downloads/credentials.json")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
    creds = flow.run_local_server(port=port, login_hint=FROM, prompt="consent", access_type="offline",
                                  authorization_prompt_message=f"Sign in as {FROM} in the browser window that opened.",
                                  success_message="Done. Regulatory Studio can now send mail. You can close this tab.")
    if not creds.refresh_token:
        raise MailError("Google did not return a refresh token; run mail-setup again")
    _save(creds)
    return str(TOKEN)


def _save(creds) -> None:
    TOKEN.write_text(creds.to_json())
    os.chmod(TOKEN, 0o600)


def _session():
    if not TOKEN.exists():
        raise NotSetUp("mail is not set up on this Mac: run  regstudio mail-setup --client ~/Downloads/credentials.json")
    from google.auth.transport.requests import AuthorizedSession, Request
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        try:
            creds.refresh(Request())
        except Exception as e:   # google.auth.exceptions.RefreshError and network errors
            raise MailError(f"Gmail sign-in has expired or was removed: run  regstudio mail-setup  again ({e})") from e
        _save(creds)
    return AuthorizedSession(creds)


# ---- sending --------------------------------------------------------------------------------------------------

def build(to: list[str], subject: str, text: str, html: str | None = None, reply_to: str | None = None) -> EmailMessage:
    m = EmailMessage()
    m["From"] = formataddr((_line(FROM_NAME, 80), _addr(FROM)))
    m["To"] = ", ".join(_addr(a) for a in to)
    if reply_to:
        m["Reply-To"] = _addr(reply_to)
    m["Subject"] = _line(subject, 180)
    m["Date"] = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    m["Message-ID"] = make_msgid(domain=FROM.split("@")[1])
    m.set_content(text)
    if html:
        m.add_alternative(html, subtype="html")
    return m


def _logged(conn, kind: str, ref: str):
    return conn.execute("SELECT status FROM mail_log WHERE kind = ? AND ref = ?", (kind, ref)).fetchone()


def send(kind: str, ref: str, to: list[str], subject: str, text: str, html: str | None = None,
         reply_to: str | None = None) -> str:
    """Sends once per (kind, ref). Returns 'sent', 'written' (outbox mode) or 'already'."""
    db.init()
    msg = build(to, subject, text, html, reply_to)
    with db.session() as conn:
        row = _logged(conn, kind, ref)
        if row and row["status"] in ("sent", "written"):
            return "already"
    if mode() == "outbox":
        OUTBOX.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{kind}-{ref}")[:120]
        (OUTBOX / f"{safe}.eml").write_bytes(bytes(msg))
        status, gid, err = "written", "", ""
    else:
        raw = base64.urlsafe_b64encode(bytes(msg)).decode()
        try:
            r = _session().post(SEND_URL, json={"raw": raw}, timeout=60)
        except MailError:
            raise
        except Exception as e:
            raise MailError(f"Gmail not reachable: {e}") from e
        if r.status_code >= 300:
            err = f"Gmail answered {r.status_code}: {r.text[:200]}"
            _record(kind, ref, msg, "failed", "", err)
            raise MailError(err)
        status, gid, err = "sent", r.json().get("id", ""), ""
    _record(kind, ref, msg, status, gid, err)
    return status


def _record(kind, ref, msg, status, gid, err):
    with db.session() as conn:
        conn.execute("""INSERT INTO mail_log(kind, ref, to_addr, subject, status, gmail_id, error) VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(kind, ref) DO UPDATE SET to_addr = excluded.to_addr, subject = excluded.subject,
                        status = excluded.status, gmail_id = excluded.gmail_id, error = excluded.error, at = datetime('now')""",
                     (kind, ref, msg["To"], msg["Subject"], status, gid, err))


def test(to: str | None = None) -> str:
    to = to or FROM
    return send("test", dt.datetime.now().strftime("%Y%m%d%H%M%S"), [to], "Regulatory Studio: mail is working",
                f"This is a test from the Regulatory Studio Mac. Mail is sent as {FROM} through the Gmail API.\n")


# ---- what the studio mails ------------------------------------------------------------------------------------

def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _table(rows: list[tuple[str, str]]) -> tuple[str, str]:
    text = "\n".join(f"{k}: {v}" for k, v in rows)
    html = "<table style='font:14px/1.5 sans-serif'>" + "".join(
        f"<tr><td style='padding:4px 14px 4px 0;color:#666;vertical-align:top'>{_esc(k)}</td>"
        f"<td style='padding:4px 0'>{_esc(v).replace(chr(10), '<br>')}</td></tr>" for k, v in rows) + "</table>"
    return text, html


def lead_mail(lead: dict) -> dict:
    rows = [("From", f"{lead.get('name') or '-'} <{lead.get('email') or '-'}>"), ("Organisation", lead.get("org") or "-"),
            ("Business", lead.get("business") or "-"), ("State", lead.get("state") or "-"), ("Asked for", lead.get("asked") or "-"),
            ("Was reading", lead.get("reading") or "-"), ("Page", lead.get("page") or "-"), ("Message", lead.get("message") or "-"),
            ("Received", str(lead.get("at") or "-"))]
    text, html = _table(rows)
    what = lead.get("asked") or lead.get("reading") or ""
    foot = f"\n\nReply to this email to answer {lead.get('name') or 'them'} directly. Mark it handled in the Inbox: {config.REVIEW_SITE.rstrip('/')}/_/inbox\n"
    reply = lead.get("email") if EMAIL.match(str(lead.get("email") or "").lower()) else None
    return {"subject": f"Regulatory Studio: project request from {lead.get('name') or 'a reader'}" + (f": {what}" if what else ""),
            "text": text + foot, "html": html + f"<p style='font:13px sans-serif;color:#666'>{_esc(foot.strip())}</p>",
            "reply_to": reply}


def chat_mail(chat: dict) -> dict:
    msgs = chat.get("messages") or []
    if isinstance(msgs, str):
        msgs = json.loads(msgs)
    lines = [f"- {m.get('text', '')}" for m in msgs if isinstance(m, dict)][-30:]   # the visitor's own messages
    rows = [("Name", chat.get("name") or "-"), ("Company", chat.get("company") or "-"), ("Reach them at", chat.get("reach") or "-"),
            ("Page", chat.get("page") or "-"), ("Started", str(chat.get("started_at") or "-"))]
    text, html = _table(rows)
    convo = "\n".join(lines)
    reach = str(chat.get("reach") or "").strip().lower()
    foot = f"Mark it handled in the Inbox: {config.REVIEW_SITE.rstrip('/')}/_/inbox"
    return {"subject": f"Regulatory Studio chat: {chat.get('name') or 'a visitor'} left contact details",
            "text": f"{text}\n\nWhat they wrote\n{convo}\n\n{foot}\n",
            "html": f"{html}<h3 style='font:600 14px sans-serif'>What they wrote</h3><pre style='font:13px/1.5 sans-serif;white-space:pre-wrap'>{_esc(convo)}</pre>"
                    f"<p style='font:13px sans-serif;color:#666'>{_esc(foot)}</p>",
            "reply_to": reach if EMAIL.match(reach) else None}


def relay() -> dict:
    """Collects new project requests and chats with contact details from the review site and mails them to SALES."""
    if not ready():
        return {"mailed": 0, "skipped": "mail not set up"}
    from . import mirror
    got = mirror.call("leads")
    done_leads, done_chats, errors = [], [], []
    for lead in got.get("leads") or []:
        try:
            m = lead_mail(lead)
            send("lead", str(lead["id"]), [SALES], m["subject"], m["text"], m["html"], m["reply_to"])
            done_leads.append(lead["id"])
        except MailError as e:
            errors.append(str(e)[:200])
            if isinstance(e, NotSetUp):
                break
    for chat in got.get("chats") or []:
        try:
            m = chat_mail(chat)
            send("chat", str(chat["id"]), [SALES], m["subject"], m["text"], m["html"], m["reply_to"])
            done_chats.append(chat["id"])
        except MailError as e:
            errors.append(str(e)[:200])
            if isinstance(e, NotSetUp):
                break
    if done_leads or done_chats:
        mirror.call("leads_mailed", leads=done_leads, chats=done_chats)
    return {"mailed": len(done_leads) + len(done_chats), **({"errors": errors} if errors else {})}


def invitation(name: str, email: str, team: str, link: str, days: int = 7, role: str = "reviewer") -> str:
    teams = {"urja": "the Urja Praxis legal review", "joulewise": "the jouleWise team's review", "admin": "Regulatory Studio, as an administrator"}
    as_role = " as a senior reviewer (your decisions take precedence)" if role == "senior" else ""
    text = (f"Dear {name},\n\nYou are invited to {teams.get(team, 'Regulatory Studio')}{as_role} at {config.REVIEW_SITE.rstrip('/')}.\n\n"
            f"Open this link to choose your password (it works once and expires in {days} days):\n{link}\n\n"
            "After that, sign in at the same address with this email and your password.\n"
            "If you did not expect this, ignore this email; nothing happens unless the link is opened.\n\n"
            f"jouleWise Regulatory Studio\n")
    html = (f"<div style='font:15px/1.6 sans-serif;max-width:560px'><p>Dear {_esc(name)},</p>"
            f"<p>You are invited to {_esc(teams.get(team, 'Regulatory Studio'))}{_esc(as_role)} at {_esc(config.REVIEW_SITE.rstrip('/'))}.</p>"
            f"<p><a href='{_esc(link)}' style='display:inline-block;background:#1f6f4a;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none'>Choose your password</a></p>"
            f"<p style='color:#666;font-size:13px'>The link works once and expires in {days} days. After that, sign in at the same address "
            "with this email and your password. If you did not expect this, ignore this email.</p></div>")
    return send("invite", link.rsplit("/", 1)[-1][:16], [email], "Your invitation to the Regulatory Studio review site", text, html)


def review_notice(to: list[str] | None = None, today: dt.date | None = None) -> str:
    """Tells reviewers what is waiting, highest priority first. Once per day per address list."""
    to = to or REVIEW_NOTIFY
    if not to:
        return "no addresses: set REGSTUDIO_MAIL_REVIEW in ops/studio.env"
    from . import priority
    today = today or dt.date.today()
    db.init()
    with db.session() as conn:
        orders = conn.execute(
            """SELECT d.id, d.commission, d.title, d.doc_date, o.significance, o.summary_status, o.summary, o.issue,
                      o.outcome, o.headline, o.topics, o.impact, o.parties
               FROM documents d JOIN orders o ON o.doc_id = d.id
               WHERE o.summary_status = 'proposed' AND d.stage IN ('read', 'drafted')""").fetchall()
        drafts = conn.execute(
            """SELECT d.id, d.commission, d.title, c.kind, c.comment_deadline, c.hearing_date, c.summary_status,
                      c.summary, c.proposes, c.amends, c.impact
               FROM documents d JOIN consultations c ON c.doc_id = d.id WHERE c.summary_status = 'proposed'""").fetchall()
    name = lambda r: config.COMMISSIONS.get(r["commission"], r["commission"])
    scored = [(priority.for_order(o, today)["score"], "Order", o["title"] or o["id"][:10], name(o)) for o in orders] + \
             [(priority.for_consultation(c, today)["score"], "Draft", c["title"] or c["id"][:10], name(c)) for c in drafts]
    if not scored:
        return "nothing waiting"
    scored.sort(key=lambda t: -t[0])
    top = scored[:8]
    site = config.REVIEW_SITE.rstrip("/") + "/urja-praxis"
    text = (f"{len(scored)} summaries are waiting for legal review. Highest priority first:\n\n"
            + "\n".join(f"{i}. [{s}] {k}, {c}: {t}" for i, (s, k, t, c) in enumerate(top, 1))
            + f"\n\nOpen the queue: {site}\n")
    html = (f"<div style='font:15px/1.6 sans-serif;max-width:620px'><p>{len(scored)} summaries are waiting for legal review. Highest priority first:</p><ol>"
            + "".join(f"<li><b>{s}</b> &middot; {_esc(k)}, {_esc(c)}: {_esc(t)}</li>" for s, k, t, c in top)
            + f"</ol><p><a href='{_esc(site)}'>Open the review queue</a></p></div>")
    return send("review", f"{today.isoformat()}:{','.join(sorted(to))}"[:200], to,
                f"Regulatory Studio: {len(scored)} waiting for review", text, html)
