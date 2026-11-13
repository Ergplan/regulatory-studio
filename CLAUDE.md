# Rules for Claude Code in this repo

Regulatory Studio publishes legal summaries under jouleWise's name. Accuracy beats speed.

## Non-negotiables

1. **The model never writes truth.** Anything Claude produces (triage verdict, summary,
   link, registry entry) lands in the working DB with status `proposed`. Only the review
   app, acting for a named reviewer, sets `approved`. Publish reads `approved` rows only.
2. **Every link cites a paragraph.** A reference without a paragraph id from the
   extracted text is dropped, not guessed.
3. **Unresolved stays unresolved.** If a cited regulation or clause is not in the registry,
   record it with `resolved = 0` and the citation as written. Never invent a clause id.
4. **No fabricated orders.** Test data lives in `pipeline/tests/fixtures/` and is marked
   SAMPLE. Never put sample data in `data/snapshot` for a production build.
5. **Downloads only land in the inbox.** `regstudio download` fetches recent orders from the
   commission sites into `data/inbox/` with the same metadata contract the download team uses;
   every later stage reads only `data/inbox/`. Be polite to the sites (robots.txt, a pause per
   host, modest `--limit`), never turn off TLS verification, and fix a broken parser rather than
   guessing fields.

## Working on the build

- Python 3.10+. Dependencies: pymupdf, jsonschema, fastapi, uvicorn, jinja2.
- Working DB is SQLite at `data/store/working.db`; schema in `pipeline/regstudio/schema.sql`.
  Change it only through a new numbered file in `pipeline/regstudio/migrations/`.
- Run `pytest pipeline/tests` before committing. Tests use `REGSTUDIO_READER=mock`. Review-screen
  tests use the real uvicorn `server` fixture, not `fastapi.testclient` (it needs httpx2, which CI
  does not install).
- The site in `web/` builds only from `data/snapshot/*.json`. Pages must be fully readable
  without JavaScript; the spider map sits on top of a plain list of links.

## The Mac mini is the server

See `docs/ARCHITECTURE.md` and `docs/MAC_MINI_SERVER.md`. Four launchd jobs (`ops/launchd/`, installed by
`ops/install_mac.sh`):

- **scan** (`ops/scan.sh`, Tuesday and Friday 06:00): download, intake, extract, registry, amend, consult,
  triage, read, check, impact, figures, comments, the Friday digest draft, then `regstudio deploy --refresh`.
  Every stage has a `--limit`; a run that hits a usage limit stops cleanly and the next scan resumes.
- **review**: `regstudio review` on 127.0.0.1:8765, reached from outside only through the Cloudflare Tunnel.
  Tunnelled requests must carry a valid Cloudflare Access token for a registered reviewer (`access.py`).
- **deploy** (every 10 minutes): `regstudio deploy` pushes approved items to `main` (public site) and the
  unreviewed preview to `preview` (preview site), each from its own git worktree in `data/store/deploy/`.
- **tunnel**: `cloudflared`.

Never weaken these: production data comes only from `approved` rows; a request through Cloudflare without a
valid token is refused; the review screen binds to 127.0.0.1; no credentials or tokens in the repo.

## Market impact and Studio comments

Both are opt-in per document (review screen button, or `regstudio run impact --doc <id>` /
`regstudio run comments --doc <id> --as <group>`), both are proposals until a reviewer approves, and
every statement cites paragraph ids of the document; uncited statements are dropped. Comment drafts
are also written as Markdown under `data/comments/<commission>/<doc>/<group>.md`.
