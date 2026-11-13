"""Optional reviewer sign-in for the review screen.

With no reviewers configured, the screen runs as before on 127.0.0.1 only, and a reviewer
types their name. Once `regstudio add-reviewer` has added anyone, every page needs a signed-in
reviewer, and the screen may be opened to the office network with `regstudio review --host 0.0.0.0`.
Passwords are stored as salted PBKDF2 hashes in data/store/reviewers.json.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time

from . import config

ROUNDS = 310_000
SESSION_HOURS = 12


def _file():
    return config.STORE / "reviewers.json"


def _load() -> dict:
    f = _file()
    return json.loads(f.read_text()) if f.exists() else {}


def enabled() -> bool:
    return bool(_load())


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ROUNDS).hex()


def add_reviewer(name: str, password: str | None = None, email: str | None = None) -> None:
    """A reviewer signs in with a password, or is recognised by the email Cloudflare Access verified, or both."""
    name = name.strip()
    email = (email or "").strip().lower()
    if not name or not (password or email):
        raise ValueError("a name and either a password or an email are required")
    if password is not None and len(password) < 10:
        raise ValueError("a password needs at least 10 characters")
    if email and "@" not in email:
        raise ValueError("that does not look like an email address")
    data = _load()
    rec = dict(data.get(name) or {})
    if password:
        salt = secrets.token_hex(16)
        rec.update(salt=salt, hash=_hash(password, salt))
    if email:
        for other, r in data.items():
            if other != name and r.get("email") == email:
                raise ValueError(f"{email} already belongs to {other}")
        rec["email"] = email
    data[name] = rec
    config.STORE.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps(data, indent=1))
    _file().chmod(0o600)


def check_password(name: str, password: str) -> bool:
    rec = _load().get(name.strip())
    if not rec or "hash" not in rec:
        _hash(password, "00" * 16)  # same work either way
        return False
    return hmac.compare_digest(rec["hash"], _hash(password, rec["salt"]))


_attempts: dict[str, list[float]] = {}


def allow_attempt(name: str, limit: int = 8, window: int = 900) -> bool:
    """At most `limit` password attempts per name in `window` seconds."""
    now = time.time()
    recent = [t for t in _attempts.get(name.strip().lower(), []) if now - t < window]
    recent.append(now)
    _attempts[name.strip().lower()] = recent
    return len(recent) <= limit


def by_email(email: str) -> str | None:
    """Reviewer name registered for an email that Cloudflare Access has verified."""
    email = (email or "").strip().lower()
    return next((n for n, r in _load().items() if email and r.get("email") == email), None)


def _secret() -> bytes:
    f = config.STORE / "review_secret"
    if not f.exists():
        config.STORE.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_hex(32))
        f.chmod(0o600)
    return bytes.fromhex(f.read_text().strip())


def make_session(name: str) -> str:
    payload = f"{name}|{int(time.time()) + SESSION_HOURS * 3600}"
    mac = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{mac}"


def read_session(token: str | None) -> str | None:
    if not token or token.count("|") < 2:
        return None
    payload, mac = token.rsplit("|", 1)
    good = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, mac):
        return None
    name, expires = payload.rsplit("|", 1)
    if not expires.isdigit() or int(expires) < time.time() or name not in _load():
        return None
    return name
