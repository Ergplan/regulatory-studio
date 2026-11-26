"""`regstudio sync`: the Mac's link to the review site on Vercel.

The review screen runs on this Mac (127.0.0.1) and is the only place a decision is ever applied. This module
keeps a copy of its pages on the review site, where signed-in reviewers read them, and brings back what they
submit there:

  1. pull   the forms reviewers submitted on the review site (in order), replay each against the local review
            screen as that reviewer, and report what happened
  2. crawl  the local review screen and push the pages (and small PDFs) that changed

Every call is made outward from this Mac and signed with this Mac's key (Ed25519); the review site holds only
the public half. Nothing connects into the Mac. An event is applied at most once: its id is recorded locally
before it is acknowledged, so a lost acknowledgement cannot apply it twice.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

LOCAL = os.environ.get("REGSTUDIO_LOCAL_REVIEW", "http://127.0.0.1:8765")
NAME_SLOT = "RSREVIEWERNAME"                 # stands in for the reviewer's name in mirrored pages
START = ["/", "/urja-praxis", "/jouleWise", "/memory"]
FOLLOW = re.compile(r'href="(/(?:order|consultation|digest|regulation|amendment)/[^"#?]+)')
# Forms a reviewer may submit from the review site. Sign-in and identity routes are never replayed.
ALLOWED = re.compile(r"^/(?:order/[0-9a-f]+/(?:summary|link)|link/\d+|regulation/.+/meta|clause/.+|digest/[0-9A-Za-z-]+(?:/note)?|"
                     r"amendment/[0-9a-f]+/meta|amendment-change/\d+|consultation/[0-9a-f]+|(?:rating|impact|comments|checks|figures|"
                     r"notes|revise|commercial)/[0-9a-f]+|(?:comment|revision|lesson)/\d+|memory|deploy)$")
MAX_PDF = 4_000_000                          # larger files are linked to the commission's site instead
CHUNK = 2_000_000
MAX_PAGES = 800


class SyncError(RuntimeError):
    pass


# ---------- keys ----------

def _key_path():
    return config.STORE / "sync_key.pem"


def public_key() -> str:
    """This Mac's public key (base64). Creates the key pair on first use; the private half never leaves the Mac."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    p = _key_path()
    if not p.exists():
        config.STORE.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key = serialization.load_pem_private_key(p.read_bytes(), password=None)
    pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    (config.STORE / "sync_public_key.txt").write_text(pub + "\n")
    return pub


def _sign(message: bytes) -> str:
    from cryptography.hazmat.primitives import serialization
    public_key()
    key = serialization.load_pem_private_key(_key_path().read_bytes(), password=None)
    return base64.b64encode(key.sign(message)).decode()


def local_token() -> str:
    """A secret shared only between this module and the local review screen, both on this Mac."""
    p = config.STORE / "mirror.token"
    if not p.exists():
        config.STORE.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32))
    return p.read_text().strip()


# ---------- talking to the review site and to the local screen ----------

def call(op: str, **body) -> dict:
    data = json.dumps({"op": op, **body}).encode()
    stamp = str(int(time.time()))
    sig = _sign(f"{stamp}\n{hashlib.sha256(data).hexdigest()}".encode())
    req = urllib.request.Request(config.REVIEW_SITE.rstrip("/") + "/review-api/sync", data=data, method="POST", headers={
        "Content-Type": "application/json", "X-Studio-Time": stamp, "X-Studio-Sig": sig, "User-Agent": "regstudio-sync"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SyncError(f"review site answered {e.code}: {e.read()[:200].decode('utf-8', 'replace')}") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise SyncError(f"review site not reachable: {e}") from e


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def local(path: str, body: bytes | None = None, who: str = NAME_SLOT, email: str | None = None,
          role: str | None = None) -> tuple[int, bytes]:
    # The reviewer's sign-in email and review role (reviewer or senior), as the review site's Admin page set them.
    req = urllib.request.Request(LOCAL + urllib.parse.quote(path, safe="/%"), data=body, method="POST" if body is not None else "GET", headers={
        "X-Studio-Mirror": local_token(), "X-Studio-Reviewer": urllib.parse.quote(who),
        **({"X-Studio-Reviewer-Email": urllib.parse.quote(email)} if email else {}),
        **({"X-Studio-Reviewer-Role": "senior" if role == "senior" else "reviewer"} if body is not None else {}),
        **({"Content-Type": "application/x-www-form-urlencoded"} if body is not None else {})})
    try:
        with _opener.open(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise SyncError(f"the local review screen is not running at {LOCAL}: {e}") from e


# ---------- state kept on this Mac ----------

def _state() -> sqlite3.Connection:
    config.STORE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.STORE / "sync_state.db", isolation_level=None)
    conn.execute("CREATE TABLE IF NOT EXISTS applied (id INTEGER PRIMARY KEY, status TEXT, note TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP)")
    try:   # when the event was made on the site: tells a new event from an old one with the same number (site database reset)
        conn.execute("ALTER TABLE applied ADD COLUMN created TEXT")
    except sqlite3.OperationalError:
        pass
    return conn


# ---------- the two halves of a sync ----------

def replay(event: dict) -> tuple[str, str]:
    path = event.get("path") or ""
    if not ALLOWED.match(path) or ".." in path:
        return "refused", "This form is not one the review site may submit."
    code, body = local(path, (event.get("body") or "").encode(), who=event.get("user_name") or "Reviewer",
                       email=event.get("user_email"), role=event.get("role"))
    if code in (200, 303):
        return "applied", ""
    try:
        detail = json.loads(body).get("detail", "")
    except ValueError:
        detail = ""
    return "failed", (str(detail) or f"The review screen answered {code}.")[:300]


def pull() -> dict:
    state = _state()
    applied = failed = 0
    while True:
        events = call("events").get("events") or []
        if not events:
            break
        results = []
        for e in sorted(events, key=lambda e: e["id"]):
            created = str(e.get("created_at") or "")
            row = state.execute("SELECT status, note, created FROM applied WHERE id = ?", (e["id"],)).fetchone()
            if row is not None and row[2] and created and row[2] != created:
                row = None                       # the same number, but a different event: the site's database was reset
            if row is None:
                status, note = replay(e)
                state.execute("INSERT OR REPLACE INTO applied(id, status, note, created) VALUES (?, ?, ?, ?)",
                              (e["id"], status, note, created))
                row = (status, note)
                applied += status == "applied"
                failed += status != "applied"
            results.append({"id": e["id"], "status": row[0], "note": row[1]})
        call("ack", results=results)
    return {"applied": applied, "failed": failed}


def crawl() -> tuple[dict[str, str], set[str]]:
    pages: dict[str, str] = {}
    files: set[str] = set()
    queue = list(START)
    while queue and len(pages) < MAX_PAGES:
        path = queue.pop(0)
        if path in pages:
            continue
        code, body = local(path)
        if code != 200:
            continue
        html = body.decode("utf-8", "replace")
        pages[path] = html
        files.update(re.findall(r'src="/file/([0-9a-f]{64})', html))
        for nxt in FOLLOW.findall(html):
            nxt = urllib.parse.unquote(nxt)
            if nxt not in pages and nxt not in queue:
                queue.append(nxt)
    return pages, files


def push(force: bool = False) -> dict:
    pages, files = crawl()
    have = call("hello", status=_status())
    known, known_files = have.get("pages") or {}, set(have.get("files") or [])
    hashed = {p: hashlib.sha256(h.encode()).hexdigest() for p, h in pages.items()}
    changed = [p for p in pages if force or known.get(p) != hashed[p]]
    batch, size, sent = [], 0, 0
    for p in changed:
        batch.append({"path": p, "html": pages[p], "hash": hashed[p]})
        size += len(pages[p])
        if size > 1_500_000:
            call("pages", pages=batch)
            sent, batch, size = sent + len(batch), [], 0
    gone = [p for p in known if p not in pages]
    if batch or gone:
        call("pages", pages=batch, remove=gone)
        sent += len(batch)
    uploaded = 0
    for doc in sorted(files - known_files):
        code, data = local(f"/file/{doc}")
        if code != 200 or len(data) > MAX_PDF:
            call("file", id=doc, n=0, total=0, data="", size=len(data) if code == 200 else 0)   # recorded as "too large"
            continue
        parts = [data[i:i + CHUNK] for i in range(0, len(data), CHUNK)] or [b""]
        for n, part in enumerate(parts):
            call("file", id=doc, n=n, total=len(parts), data=base64.b64encode(part).decode(), size=len(data))
        uploaded += 1
    return {"pages": len(pages), "sent": sent, "removed": len(gone), "pdfs": uploaded}


def _status() -> dict:
    out = {}
    for name in ("scan_last.json", "deploy_last.json"):
        f = config.STORE / name
        try:
            out[name.split("_")[0]] = json.loads(f.read_text()) if f.exists() else None
        except ValueError:
            pass
    from . import mailer
    out["mail"] = mailer.FROM if mailer.ready() else None   # the admin page shows whether invitations can be emailed
    return out


def _fingerprint() -> float:
    newest = 0.0
    for name in ("working.db", "working.db-wal", "scan_last.json", "deploy_last.json"):
        f = config.STORE / name
        if f.exists():
            newest = max(newest, f.stat().st_mtime)
    return newest


def _mail() -> dict:
    """Mails new project requests and chat contacts to sales (Gmail, mailer.py). Never stops the sync."""
    from . import mailer
    if not mailer.ready():
        return {}
    try:
        out = mailer.relay()
        invited = invite_requests()
    except (mailer.MailError, SyncError) as e:
        return {"mail_error": str(e)[:200]}
    got = {"mailed": out["mailed"]} if out.get("mailed") else ({"mail_error": out["errors"][0]} if out.get("errors") else {})
    return {**got, **({"invited": invited} if invited else {})}


def invite_requests() -> int:
    """Invitations an administrator asked for on the review site's Admin page with "Email the invitation".
    The token is made here, so the site never holds a usable link; the Mac emails it to the reviewer."""
    from . import mailer
    done = []
    for r in call("invite_requests").get("requests") or []:
        try:
            role = "senior" if r.get("role") == "senior" else "reviewer"
            link = invite(r["name"], r["email"], r["team"], role=role)
            status = mailer.invitation(r["name"], r["email"], r["team"], link, role=role)
            done.append({"id": r["id"], "status": "emailed" if status in ("sent", "written") else status, "note": ""})
        except (mailer.MailError, SyncError, KeyError) as e:
            done.append({"id": r.get("id"), "status": "failed", "note": str(e)[:200]})
    if done:
        call("invite_requests_done", results=done)
    return sum(d["status"] == "emailed" for d in done)


def once(force: bool = False) -> dict:
    got = pull()
    return {**got, **push(force), **_mail()}


def loop(every: int = 20) -> None:
    """Runs for ever: decisions are applied within `every` seconds, and pages are pushed when something changed.
    New requests from the public site are mailed to sales about once a minute."""
    seen, last_full, last_mail = -1.0, 0.0, 0.0
    while True:
        try:
            if time.time() - last_mail > 60:
                last_mail = time.time()
                mailed = _mail()
                if mailed:
                    print(time.strftime("%Y-%m-%d %H:%M:%S"), json.dumps(mailed), flush=True)
            got = pull()
            mark = _fingerprint()
            if got["applied"] or got["failed"] or mark != seen or time.time() - last_full > 600:
                out = push()
                seen, last_full = _fingerprint(), time.time()
                if got["applied"] or got["failed"] or out["sent"] or out["pdfs"]:
                    print(time.strftime("%Y-%m-%d %H:%M:%S"), json.dumps({**got, **out}), flush=True)
            else:
                call("hello", status=_status(), light=True)            # heartbeat
        except SyncError as e:
            print(time.strftime("%Y-%m-%d %H:%M:%S"), "waiting:", e, flush=True)
            time.sleep(min(120, every * 3))
        time.sleep(every)


def invite(name: str, email: str, team: str = "urja", days: int = 7, role: str = "reviewer") -> str:
    """Creates a one-time invitation on the review site and returns its link. The reviewer sets their own password."""
    token = secrets.token_urlsafe(32)
    call("invite", name=name.strip(), email=email.strip().lower(), team=team, role="senior" if role == "senior" else "reviewer",
         token_hash=hashlib.sha256(token.encode()).hexdigest(), days=days)
    return f"{config.REVIEW_SITE.rstrip('/')}/_/invite/{token}"
