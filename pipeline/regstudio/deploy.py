"""Push what the legal team approved to the public site, and the unreviewed preview to the preview site.

The Mac mini is the server. Vercel only builds what is in git:
  - branch `main`    -> the public site.  Its data/snapshot holds approved items only.
  - branch `preview` -> the preview site. Same code, with a snapshot that also shows proposed
                        items, each marked as awaiting review.

Each push is made in its own git worktree under data/store/deploy, so the working folder (and any
edits in it) is never touched. A push happens only when the published data changed. The preview
branch is rebuilt each time as "main plus the preview data" and replaced on the remote.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import shutil
import subprocess
from pathlib import Path

from . import config, db, publish

TARGETS = ("production", "preview")
VOLATILE = ("data/snapshot/site.json",)   # carries the time of writing; not a change worth a build by itself


class DeployError(Exception):
    pass


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    if check and r.returncode:
        raise DeployError(f"git {' '.join(args[:3])}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout.strip()


def _has(cwd: Path, ref: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=cwd, capture_output=True).returncode == 0


def _worktree(name: str, base: str) -> Path:
    wt = config.STORE / "deploy" / name
    if not (wt / ".git").exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(config.GIT_ROOT, "worktree", "prune")
        _git(config.GIT_ROOT, "worktree", "add", "--detach", "--force", str(wt), base)
    _git(wt, "reset", "--hard", "--quiet")
    _git(wt, "checkout", "--detach", "--quiet", base)
    _git(wt, "clean", "-fdq", "data/snapshot")
    return wt


def _counts(snapshot: Path) -> dict:
    out = {}
    for name in ("orders", "consultations", "regulations", "digests"):
        f = snapshot / f"{name}.json"
        out[name] = len(json.loads(f.read_text())) if f.exists() else 0
    return out


def _push(target: str, refresh: bool) -> dict:
    remote, main = config.GIT_REMOTE, config.BRANCH_PRODUCTION
    branch = main if target == "production" else config.BRANCH_PREVIEW
    base = f"{remote}/{main}"
    wt = _worktree(target, base)

    staging = config.STORE / "deploy" / "out" / target
    shutil.rmtree(staging, ignore_errors=True)
    publish.run(clean=True, preview=(target == "preview"), out=staging)   # production: approved rows only, by construction
    live = wt / "data" / "snapshot"
    shutil.rmtree(live, ignore_errors=True)
    shutil.copytree(staging, live)
    _git(wt, "add", "-A", "-f", "data/snapshot")

    against = f"{remote}/{branch}" if _has(wt, f"refs/remotes/{remote}/{branch}") else None
    changed = _git(wt, "diff", "--cached", "--name-only", against or base).splitlines() if against else ["(new branch)"]
    real = [f for f in changed if f not in VOLATILE]
    counts = _counts(live)
    if not real and not refresh:
        return {"pushed": False, "reason": "nothing changed", **counts}

    what = "Publish approved items" if target == "production" else "Preview: unreviewed items for the legal team"
    _git(wt, "commit", "--quiet", "--allow-empty", "-m",
         f"{what}\n\n{counts['orders']} orders, {counts['consultations']} drafts, {counts['regulations']} regulations, "
         f"{counts['digests']} digests. Pushed by regstudio deploy on the Mac mini.")
    if target == "production":
        _git(wt, "push", "--quiet", remote, f"HEAD:refs/heads/{branch}")          # refused if main moved: the next run retries
    else:
        lease = f"--force-with-lease=refs/heads/{branch}" + (f":{_git(wt, 'rev-parse', against)}" if against else ":")
        _git(wt, "push", "--quiet", lease, remote, f"HEAD:refs/heads/{branch}")
    return {"pushed": True, "commit": _git(wt, "rev-parse", "--short", "HEAD"), "files": len(real), **counts}


def last() -> dict:
    f = config.STORE / "deploy_last.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {}


def run(targets: list[str] | None = None, refresh: bool = False) -> dict:
    """Publish and push each target. One run at a time; a second caller returns at once."""
    targets = targets or list(TARGETS)
    (config.STORE / "deploy").mkdir(parents=True, exist_ok=True)
    out: dict = {}
    with open(config.STORE / "deploy" / "lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {t: {"pushed": False, "reason": "another deploy is running"} for t in targets}
        state = last()
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            _git(config.GIT_ROOT, "fetch", "--quiet", "--prune", config.GIT_REMOTE)
        except (DeployError, subprocess.TimeoutExpired, OSError) as e:
            out = {t: {"pushed": False, "error": str(e)[:400]} for t in targets}
        else:
            for t in targets:
                try:
                    out[t] = _push(t, refresh)
                except (DeployError, subprocess.TimeoutExpired, OSError, ValueError) as e:
                    out[t] = {"pushed": False, "error": str(e)[:400]}
        for t, r in out.items():
            prev = state.get(t, {})
            state[t] = {**r, "checked_at": now, "pushed_at": now if r.get("pushed") else prev.get("pushed_at"),
                        "commit": r.get("commit") or prev.get("commit")}
        (config.STORE / "deploy_last.json").write_text(json.dumps(state, indent=1))
        with db.session() as conn:
            for t, r in out.items():
                if r.get("pushed") or r.get("error"):
                    db.audit(conn, "pipeline", "deploy", t, {k: r[k] for k in ("commit", "error", "orders", "consultations") if k in r})
    return out
