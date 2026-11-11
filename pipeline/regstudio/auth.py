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


def add_reviewer(name: str, password: str) -> None:
    name = name.strip()
    if not name or len(password) < 10:
        raise ValueError("a name and a password of at least 10 characters are required")
    data = _load()
    salt = secrets.token_hex(16)
    data[name] = {"salt": salt, "hash": _hash(password, salt)}
    config.STORE.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps(data, indent=1))
    _file().chmod(0o600)


def check_password(name: str, password: str) -> bool:
    rec = _load().get(name.strip())
    if not rec:
        _hash(password, "00" * 16)  # same work either way
        return False
    return hmac.compare_digest(rec["hash"], _hash(password, rec["salt"]))


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
