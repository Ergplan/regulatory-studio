"""Cloudflare Access in front of the review screen.

The Mac mini has no fixed address, so the review screen is reached through a Cloudflare Tunnel,
and Cloudflare Access asks each visitor to prove their email before a request is let through.
Every request that Access lets through carries a signed token. This module checks that token
(signature, audience, issuer, expiry) and returns the email in it, so the screen never trusts
a header that anyone could type.

Set REGSTUDIO_ACCESS_TEAM (the team name, as in <team>.cloudflareaccess.com) and
REGSTUDIO_ACCESS_AUD (the application's audience tag) to turn it on.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

from . import config

HEADER = "cf-access-jwt-assertion"
CLOUDFLARE_HEADERS = ("cf-connecting-ip", "cf-ray", HEADER)  # set by Cloudflare's edge on every tunnelled request
_cache: dict = {"at": 0.0, "keys": {}}


class AccessError(Exception):
    pass


def team_domain() -> str:
    t = os.environ.get("REGSTUDIO_ACCESS_TEAM", "").strip().removeprefix("https://").strip("/")
    return t if not t or "." in t else f"{t}.cloudflareaccess.com"


def audience() -> str:
    return os.environ.get("REGSTUDIO_ACCESS_AUD", "").strip()


def configured() -> bool:
    return bool(team_domain() and audience())


def through_cloudflare(headers) -> bool:
    return any(h in headers for h in CLOUDFLARE_HEADERS)


def _fetch_keys() -> dict:
    with urllib.request.urlopen(f"https://{team_domain()}/cdn-cgi/access/certs", timeout=10) as r:
        return json.load(r)


def _keys(refresh: bool = False) -> dict:
    """Signing keys by key id, cached for an hour and kept on disk so a brief network fault does not lock reviewers out."""
    import jwt
    disk = config.STORE / "access_certs.json"
    if refresh or time.time() - _cache["at"] > 3600 or not _cache["keys"]:
        try:
            data = _fetch_keys()
            config.STORE.mkdir(parents=True, exist_ok=True)
            disk.write_text(json.dumps(data))
        except Exception as e:  # network fault: fall back to the last keys we saw
            if not disk.exists():
                raise AccessError(f"cannot fetch Cloudflare Access keys: {e}") from e
            data = json.loads(disk.read_text())
        _cache.update(at=time.time(), keys={k["kid"]: jwt.PyJWK(k).key for k in data.get("keys", [])})
    return _cache["keys"]


def verify(token: str | None) -> str:
    """Email of the person Cloudflare Access let through. Raises AccessError for anything else."""
    if not configured():
        raise AccessError("Cloudflare Access is not configured on this machine")
    if not token:
        raise AccessError("no Cloudflare Access token on the request")
    try:
        import jwt
    except ImportError as e:
        raise AccessError("install the access extra: pip install -e 'pipeline[access]'") from e
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = _keys().get(kid) or _keys(refresh=True).get(kid)   # keys rotate: look once more before refusing
        if key is None:
            raise AccessError("token signed with an unknown key")
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=audience(), issuer=f"https://{team_domain()}",
                            options={"require": ["exp", "iat", "aud", "iss"]})
    except jwt.PyJWTError as e:
        raise AccessError(f"token rejected: {e}") from e
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise AccessError("token carries no email (service tokens cannot review)")
    return email
