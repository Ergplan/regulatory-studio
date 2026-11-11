"""HTTP client for commission websites: polite, verified, cookie-aware."""

from __future__ import annotations

import http.cookiejar
import ssl
import socket
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import re

from .. import config

USER_AGENT = "Mozilla/5.0 (compatible; RegulatoryStudio/0.1; +https://github.com/Ergplan/regulatory-studio)"
PAUSE_S = 3.0


def _extra_file():
    return config.STORE / "ca_intermediates.pem"


def tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Intermediates we add are not trust anchors: every chain must still end at a system root.
    if hasattr(ssl, "VERIFY_X509_PARTIAL_CHAIN"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    if _extra_file().exists():
        ctx.load_verify_locations(cafile=str(_extra_file()))
    return ctx


def _decode(pem: str) -> dict:
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(pem)
    try:
        return ssl._ssl._test_decode_cert(f.name)  # noqa: SLF001 - stdlib decoder, read-only
    finally:
        os.unlink(f.name)


def _handshake_ok(host: str) -> bool:
    try:
        with socket.create_connection((host, 443), timeout=30) as sock:
            with tls_context().wrap_socket(sock, server_hostname=host):
                return True
    except ssl.SSLCertVerificationError:
        return False


def fetch_missing_intermediates(host: str) -> int:
    """For a site that omits its intermediate certificate, fetch it from the CA Issuers address
    in the site's own certificate (AIA), one level at a time, until the chain verifies.

    Only intermediates are kept: a self-signed (root) certificate or a PKCS#7 bundle is never
    added, so trust still has to end at a root the operating system already trusts.
    Returns how many certificates were added (0 if the chain still does not verify)."""
    current = ssl.get_server_certificate((host, 443), timeout=30)
    existing = _extra_file().read_text() if _extra_file().exists() else ""
    added = 0
    for _ in range(3):
        info = _decode(current)
        issuers = [u for u in info.get("caIssuers", ()) if u.startswith("http")]
        if not issuers:
            break
        raw = urllib.request.urlopen(issuers[0], timeout=30).read()
        if raw.startswith(b"-----BEGIN CERTIFICATE"):
            pem = raw.decode()
        elif raw[:1] == b"\x30" and not issuers[0].lower().endswith((".p7c", ".p7b")):
            pem = ssl.DER_cert_to_PEM_cert(raw)
        else:
            break  # PKCS#7 bundles carry roots; don't add those
        try:
            issued = _decode(pem)
        except ssl.SSLError:
            break
        if issued.get("subject") == issued.get("issuer"):
            break  # a root: must already be trusted by the system, never added here
        if pem.strip() not in existing:
            existing += ("" if existing.endswith("\n") or not existing else "\n") + pem
            added += 1
            config.STORE.mkdir(parents=True, exist_ok=True)
            _extra_file().write_text(existing)
        if _handshake_ok(host):
            return added or 1
        current = pem
    return 0


def robots_rules(text: str, agent: str = "regulatorystudio") -> list[tuple[bool, str]]:
    """Rules for our agent (or '*') from robots.txt, as (allow, path pattern) pairs."""
    groups, agents, rules, in_rules = {}, [], [], False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                for a in agents:
                    groups.setdefault(a, []).extend(rules)
                agents, rules, in_rules = [], [], False
            agents.append(val.lower())
        elif key in ("allow", "disallow"):
            in_rules = True
            if val:
                rules.append((key == "allow", val))
    for a in agents:
        groups.setdefault(a, []).extend(rules)
    mine = next((r for a, r in groups.items() if a != "*" and a in agent), None)
    return mine if mine is not None else groups.get("*", [])


def robots_allows(rules: list[tuple[bool, str]], path: str) -> bool:
    """RFC 9309: the longest matching rule wins; on a tie, allow wins."""
    best = None
    for allow, pattern in rules:
        rx = "^" + re.escape(pattern).replace(r"\*", ".*")
        rx = rx[:-2] + "$" if rx.endswith(r"\$") else rx
        if re.match(rx, path):
            key = (len(pattern), allow)
            best = key if best is None or key > best else best
    return best is None or best[1]


class Client:
    def __init__(self, pause_s: float = PAUSE_S):
        self.pause_s = pause_s
        self.jar = http.cookiejar.CookieJar()
        self._last: dict[str, float] = {}
        self._robots: dict[str, list[tuple[bool, str]]] = {}
        self._build()

    def _build(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=tls_context()), urllib.request.HTTPCookieProcessor(self.jar))
        self.opener.addheaders = [("User-Agent", USER_AGENT)]

    def _wait(self, host: str):
        gap = time.monotonic() - self._last.get(host, 0)
        if gap < self.pause_s:
            time.sleep(self.pause_s - gap)
        self._last[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            try:
                raw = self._open(base + "/robots.txt", check_robots=False).decode("utf-8", "ignore")
            except urllib.error.HTTPError as e:
                raw = "" if e.code < 500 else "User-agent: *\nDisallow: /"  # 4xx: no rules; 5xx: stay out
            self._robots[base] = robots_rules(raw)
        path = parts.path or "/"
        return robots_allows(self._robots[base], path + (f"?{parts.query}" if parts.query else ""))

    def _open(self, url: str, data: bytes | None = None, headers: dict | None = None, check_robots: bool = True,
              timeout: int = 120) -> bytes:
        if check_robots and not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        host = urllib.parse.urlsplit(url).hostname or ""
        req = urllib.request.Request(url, data=data, headers=headers or {})
        for attempt in range(3):
            self._wait(host)
            try:
                with self.opener.open(req, timeout=timeout) as r:
                    return r.read()
            except urllib.error.URLError as e:
                reason = getattr(e, "reason", None)
                if isinstance(reason, ssl.SSLCertVerificationError) and attempt == 0:
                    if fetch_missing_intermediates(host):
                        self._build()
                        continue
                    raise
                if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                    raise
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        raise RuntimeError("unreachable")

    def get(self, url: str, headers: dict | None = None) -> bytes:
        return self._open(url, headers=headers)

    def post(self, url: str, form: dict, headers: dict | None = None) -> bytes:
        return self._open(url, data=urllib.parse.urlencode(form).encode(), headers=headers)
