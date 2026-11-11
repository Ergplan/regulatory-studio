"""HTTP client for commission websites: polite, verified, cookie-aware."""

from __future__ import annotations

import http.cookiejar
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

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


def fetch_missing_intermediates(host: str) -> int:
    """For a site that omits its intermediate certificate, fetch it from the CA Issuers address
    in the site's own certificate (AIA). Returns how many certificates were added."""
    import tempfile
    leaf_pem = ssl.get_server_certificate((host, 443), timeout=30)
    added, current = 0, leaf_pem
    existing = _extra_file().read_text() if _extra_file().exists() else ""
    for _ in range(3):
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
            f.write(current)
        info = ssl._ssl._test_decode_cert(f.name)  # noqa: SLF001 - stdlib decoder, read-only
        issuers = [u for u in info.get("caIssuers", ()) if u.startswith("http")]
        if not issuers:
            break
        der = urllib.request.urlopen(issuers[0], timeout=30).read()
        pem = der.decode() if der.startswith(b"-----BEGIN") else ssl.DER_cert_to_PEM_cert(der)
        if pem.strip() in existing:
            break
        existing += pem
        added += 1
        current = pem
    if added:
        config.STORE.mkdir(parents=True, exist_ok=True)
        _extra_file().write_text(existing)
    return added


class Client:
    def __init__(self, pause_s: float = PAUSE_S):
        self.pause_s = pause_s
        self.jar = http.cookiejar.CookieJar()
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
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
            rp = urllib.robotparser.RobotFileParser()
            try:
                raw = self._open(base + "/robots.txt", check_robots=False).decode("utf-8", "ignore")
                rp.parse(raw.splitlines())
                self._robots[base] = rp
            except Exception:
                self._robots[base] = None  # no robots.txt: allowed
        rp = self._robots[base]
        return rp is None or rp.can_fetch(USER_AGENT, url)

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
