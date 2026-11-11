"""Command line: regstudio init | status | run <stages...> | review | publish."""

from __future__ import annotations

import argparse
import json
import sys

from . import config, db

STAGES = ["intake", "extract", "registry", "amend", "triage", "read", "draft"]


def _run_stage(name: str, limit: int | None) -> dict:
    if name == "intake":
        from . import intake
        r = intake.run(limit)
        out = {"added": len(r.added), "duplicates": r.duplicates, "rejected": len(r.rejected)}
        for path, why in r.rejected:
            print(f"  rejected {path}: {why}", file=sys.stderr)
        return out
    if name == "extract":
        from . import extract
        return extract.run(limit)
    if name == "registry":
        from . import registry
        return registry.run(limit)
    if name == "amend":
        from . import amend
        return amend.run(limit)
    if name == "triage":
        from . import triage
        return triage.run(limit)
    if name == "read":
        from . import reader
        return reader.run(limit)
    if name == "draft":
        from . import drafting
        return drafting.run(limit)
    raise SystemExit(f"unknown stage {name}")


def status() -> dict:
    with db.session() as conn:
        stages = {r["stage"]: r["n"] for r in conn.execute(
            "SELECT stage, count(*) AS n FROM documents GROUP BY stage")}
        review = {
            "summaries_proposed": conn.execute(
                "SELECT count(*) FROM orders WHERE summary_status = 'proposed'").fetchone()[0],
            "links_proposed": conn.execute(
                "SELECT count(*) FROM links WHERE status = 'proposed'").fetchone()[0],
            "clauses_proposed": conn.execute(
                "SELECT count(*) FROM clauses WHERE status = 'proposed'").fetchone()[0],
            "approved_orders": conn.execute(
                "SELECT count(*) FROM orders WHERE summary_status = 'approved'").fetchone()[0],
        }
        errors = [dict(r) for r in conn.execute(
            "SELECT id, commission, title, error FROM documents WHERE stage = 'error' LIMIT 20")]
    out = {"stages": stages, "review": review, "errors": errors}
    last = config.STORE / "download_last.json"
    if last.exists():
        d = json.loads(last.read_text())
        out["last_download"] = {"at": d.get("at"), **{
            k: {"newest": v.get("newest"), "downloaded": v.get("downloaded", 0),
                **({"problems": v.get("errors", []) + v.get("warnings", [])} if v.get("errors") or v.get("warnings") else {})}
            for k, v in d.get("sites", {}).items()}}
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="regstudio", description="Regulatory Studio pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create or migrate the working database")
    sub.add_parser("status", help="documents per stage and the review queue")
    sub.add_parser("check-inbox", help="dry run: list problems in data/inbox without registering anything")
    dl = sub.add_parser("download", help="fetch new orders from commission websites into data/inbox")
    dl.add_argument("--commission", action="append", choices=["cerc", "uperc", "rerc", "merc", "gerc", "kerc"],
                    help="repeat to pick several; default all")
    dl.add_argument("--since", default=None, help="YYYY-MM-DD; default 14 days ago")
    dl.add_argument("--limit", type=int, default=None, help="max new documents per commission")
    dl.add_argument("--dry-run", action="store_true", help="list what would be downloaded")
    r = sub.add_parser("run", help="run one or more stages in order")
    r.add_argument("stages", nargs="+", choices=STAGES)
    r.add_argument("--limit", type=int, default=None, help="max documents per stage this run")
    rv = sub.add_parser("review", help="start the legal review screen")
    rv.add_argument("--host", default="127.0.0.1")
    rv.add_argument("--port", type=int, default=8765)
    ar = sub.add_parser("add-reviewer", help="add or reset a reviewer's password (turns on sign-in)")
    ar.add_argument("name")
    pb = sub.add_parser("publish", help="write approved items to data/snapshot")
    pb.add_argument("--clean", action="store_true", help="drop sample documents from the snapshot")
    sd = sub.add_parser("send-digest", help="email an approved, published digest via Resend")
    sd.add_argument("--week", default=None, help="digest id such as 2026-W46; default the latest published")
    sd.add_argument("--send", action="store_true", help="send now; without it a draft broadcast is created")
    args = p.parse_args(argv)

    config.ensure_dirs()
    if args.cmd == "init":
        db.init()
        print(f"working database ready at {config.DB_PATH}")
    elif args.cmd == "download":
        import datetime as dt
        from . import download
        since = dt.date.fromisoformat(args.since) if args.since else None
        report = download.run(args.commission, since, args.limit, args.dry_run)
        if not args.dry_run:
            last = config.STORE / "download_last.json"
            prev = json.loads(last.read_text()).get("sites", {}) if last.exists() else {}
            last.write_text(json.dumps({"at": dt.datetime.now().isoformat(timespec="minutes"),
                                        "sites": {**prev, **report}}, indent=1, ensure_ascii=False))
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.cmd == "check-inbox":
        from . import intake
        report = intake.check()
        print(json.dumps(report, indent=2))
        if report["problems"] or report["metadata_without_pdf"] or report["misplaced_files"]:
            raise SystemExit(1)
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2))
    elif args.cmd == "run":
        db.init()
        for s in args.stages:
            print(s, json.dumps(_run_stage(s, args.limit)))
    elif args.cmd == "add-reviewer":
        import getpass
        from . import auth
        pw = getpass.getpass(f"Password for {args.name} (10+ characters): ")
        if pw != getpass.getpass("Again: "):
            raise SystemExit("passwords differ")
        auth.add_reviewer(args.name, pw)
        print(f"{args.name} added; the review screen now requires sign-in")
    elif args.cmd == "review":
        from . import auth
        db.init()  # apply any pending migrations before serving
        if args.host not in ("127.0.0.1", "localhost") and not auth.enabled():
            raise SystemExit("add at least one reviewer (regstudio add-reviewer NAME) before opening the review screen to the network")
        import uvicorn
        from .review_app import app
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.cmd == "publish":
        from . import publish
        print(json.dumps(publish.run(clean=args.clean), indent=2))
    elif args.cmd == "send-digest":
        from . import send_digest
        try:
            print(json.dumps(send_digest.run(args.week, args.send), indent=2))
        except send_digest.DigestError as e:
            raise SystemExit(f"send-digest: {e}")


if __name__ == "__main__":
    main()
