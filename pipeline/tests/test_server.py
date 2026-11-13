"""The Mac mini as the server: review screen behind Cloudflare Access, and approved items pushed to the site's git branches."""
import json
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from regstudio import config
from test_review_publish import _db, _ids, server  # noqa: F401  (fixture)


def _request(url, token=None, data=None, cloudflare=True):
    headers = {"Cf-Connecting-Ip": "203.0.113.9"} if cloudflare else {}
    if token:
        headers["Cf-Access-Jwt-Assertion"] = token
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers)) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_review_screen_behind_cloudflare_needs_a_valid_token_for_a_registered_reviewer(server, monkeypatch):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from regstudio import access, auth
    key, stranger = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())) | {"kid": "k1", "alg": "RS256", "use": "sig"}
    monkeypatch.setattr(access, "_fetch_keys", lambda: {"keys": [jwk]})
    monkeypatch.setattr(access, "_cache", {"at": 0.0, "keys": {}})
    monkeypatch.setenv("REGSTUDIO_ACCESS_TEAM", "studio")
    monkeypatch.setenv("REGSTUDIO_ACCESS_AUD", "aud-123")

    def token(email="legal@firm.example", aud="aud-123", exp=600, signer=key, iss="https://studio.cloudflareaccess.com"):
        now = int(time.time())
        return jwt.encode({"email": email, "aud": [aud], "iss": iss, "iat": now, "exp": now + exp}, signer, algorithm="RS256", headers={"kid": "k1"})

    auth.add_reviewer("Legal One", email="Legal@Firm.example")
    doc, _, _ = _ids()
    url = server.url
    assert _request(url + "/")[0] == 403                                   # through Cloudflare with no token
    assert _request(url + "/", "not-a-token")[0] == 403
    assert _request(url + "/", token(aud="another-app"))[0] == 403         # token for a different application
    assert _request(url + "/", token(exp=-60))[0] == 403                   # expired
    assert _request(url + "/", token(signer=stranger))[0] == 403           # signed by someone else
    assert _request(url + "/", token(iss="https://evil.example"))[0] == 403
    code, page = _request(url + "/", token(email="visitor@elsewhere.example"))
    assert code == 403 and "not registered as a reviewer" in page          # Access let them in, the studio does not know them
    code, page = _request(url + "/", token())
    assert code == 200 and "Reviewing as <b>Legal One</b>" in page
    body = b"action=approve&summary=Reviewed.&issue=i&outcome=o"
    assert _request(url + f"/order/{doc}/summary", token(), body)[0] == 200  # redirect followed back to the order
    assert _db().execute("SELECT reviewer, summary_status FROM orders WHERE doc_id = ?", (doc,)).fetchone()[:] == ("Legal One", "approved")
    # the email reviewer has no password, so the sign-in form on the office network does not accept them
    assert not auth.check_password("Legal One", "anything at all")

    monkeypatch.delenv("REGSTUDIO_ACCESS_AUD")                              # Access not configured: tunnelled requests are refused, never trusted
    assert _request(url + "/", token())[0] == 403


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def site_repo(server, tmp_path, monkeypatch):
    """A clone with a bare 'GitHub' beside it, standing in for the repository Vercel builds from."""
    from regstudio import deploy
    remote, clone = tmp_path / "github.git", tmp_path / "clone"
    _git(tmp_path, "init", "--quiet", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "init", "--quiet", "-b", "main", str(clone))
    for k, v in (("user.name", "Mac mini"), ("user.email", "mini@example.invalid")):
        _git(clone, "config", k, v)
    (clone / "data" / "snapshot").mkdir(parents=True)
    (clone / "data" / "snapshot" / "orders.json").write_text("[]")
    (clone / "README.md").write_text("site code")
    _git(clone, "add", "-A"); _git(clone, "commit", "--quiet", "-m", "code"); _git(clone, "remote", "add", "origin", str(remote)); _git(clone, "push", "--quiet", "origin", "main")
    monkeypatch.setattr(config, "GIT_ROOT", clone)
    from regstudio import publish
    monkeypatch.setattr(publish, "SAMPLE_MARK", "no-document-matches-this")   # deploy always drops SAMPLE documents; the fixtures are SAMPLE
    return server, remote, clone, deploy


def test_only_approved_items_reach_the_public_branch_and_the_preview_branch_shows_the_rest(site_repo):
    server, remote, clone, deploy = site_repo
    doc, _, _ = _ids()
    show = lambda branch, f="orders.json": json.loads(_git(remote, "show", f"{branch}:data/snapshot/{f}"))

    out = deploy.run()                                              # first run writes the full, empty set of data files
    assert out["production"]["orders"] == 0 and out["preview"]["pushed"] is True
    assert deploy.run()["production"]["pushed"] is False            # nothing approved since: the public site is not touched
    assert show("main") == [] and show("preview")[0]["draft"] is True and show("preview", "site.json")["preview"] is True
    before = _git(remote, "rev-parse", "main")

    server("/whoami", {"name": "Test Reviewer"})
    server(f"/order/{doc}/summary", {"action": "approve", "summary": "Reviewed.", "issue": "i", "outcome": "o"})
    out = deploy.run()
    assert out["production"]["pushed"] is True and out["production"]["orders"] == 1
    assert [o["summary"] for o in show("main")] == ["Reviewed."] and not show("main")[0].get("draft")
    assert _git(remote, "rev-parse", "main") != before
    assert _git(remote, "show", "main:README.md") == "site code"   # code is carried, only the data changed
    assert _git(clone, "status", "--porcelain") == ""              # the working folder was never touched

    again = deploy.run()
    assert again["production"] == {"pushed": False, "reason": "nothing changed", **{k: again["production"][k] for k in ("orders", "consultations", "regulations", "digests")}}
    assert again["preview"]["pushed"] is False
    assert deploy.run(refresh=True)["production"]["pushed"] is True  # scan days push anyway so day counts stay right
    assert deploy.last()["production"]["commit"]
    assert "Public site" in server.get("/") and "Push approved items now" in server.get("/")


def test_a_failed_push_is_reported_and_retried_later(site_repo):
    server, remote, clone, deploy = site_repo
    _git(clone, "remote", "set-url", "origin", str(remote) + "-gone")
    out = deploy.run()
    assert out["production"]["pushed"] is False and out["production"]["error"]
    assert "last push failed" in server.get("/")
    _git(clone, "remote", "set-url", "origin", str(remote))
    assert deploy.run()["preview"]["pushed"] is True
