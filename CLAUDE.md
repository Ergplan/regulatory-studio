# Rules for Claude Code in this repo

Regulatory Studio publishes legal summaries under jouleWise's name. Accuracy beats speed.

## Non-negotiables

1. **The model never writes truth.** Anything Claude produces (triage verdict, summary,
   link, registry entry) lands in the working DB with status `proposed`. Only the review
   app, acting for a named reviewer, sets `approved`. Publish reads `approved` rows, plus
   orders a named person flagged with `regstudio publish-pending`: those go out as drafts
   marked "awaiting legal review", with no reviewer name or approval date. Never present
   an unreviewed item as reviewed.
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

## The Mac mini is the server; reviewers work on Vercel

See `docs/ARCHITECTURE.md`. Four launchd jobs (`ops/launchd/`, installed by `ops/install_mac.sh`; `ops/start.sh`
does everything in one command):

- **scan** (`ops/scan.sh`, Tuesday and Friday 06:00): download, intake, extract, registry, amend, consult,
  triage, read, check, impact, figures, comments, revise, learn, commercial, the Friday digest draft, then
  `regstudio deploy --refresh`. Every stage has a `--limit`; a run that hits a usage limit stops cleanly and the
  next scan resumes.
- **review**: `regstudio review` on 127.0.0.1:8765. It is the only place a decision is applied.
- **sync** (`regstudio sync --loop`, `mirror.py`): the link to the review site, `review.joulewise.tech`
  (`web/app/r`, `web/app/review-api/sync`, `web/lib/review`, Postgres). It pushes copies of the review pages
  there and replays, in order and at most once, the forms signed-in reviewers submit there, as that reviewer.
  Only outward calls, signed with this Mac's Ed25519 key; the site holds the public half
  (`STUDIO_SYNC_PUBLIC_KEY`). The form allowlist is in `mirror.ALLOWED` and again in the route (`FORMS`):
  change both together.
- **deploy** (every 10 minutes): `regstudio deploy` pushes approved items to `main` (public site) and the
  unreviewed preview to `preview` (preview site), each from its own git worktree in `data/store/deploy/`.

Never weaken these: production data comes only from `approved` rows; the review screen binds to 127.0.0.1;
the review site accepts nothing from the Mac without a valid signature and nothing from a browser without a
session; passwords, sessions and invitations are stored only as hashes; no credentials, keys or tokens in the
repo (`data/store/sync_key.pem` and `mirror.token` never leave the Mac).

## Prepared files and the weekly digest

A file in `data/reader_outputs/` named `<doc id>.<step>.json` (triage, read, headline, impact, figures,
check.fact, check.legal, revise, learn, commercial) or `<week>.digest.json` is used instead of asking Claude, in file mode and in
Claude mode, so work prepared in advance is not redone by a scheduled run. It is still a proposal.

The Friday `draft` stage builds the edition: items read since the last approved edition (six-week look-back),
a lead, key points, numbers, up to three charts across documents and dates to watch. Each cites
`{doc, pid}`; anything uncited, or a number not found in its document, is dropped. To prepare an edition
early: `REGSTUDIO_EDITION_DAY=2026-11-20 regstudio run draft`. `regstudio promote <id>` sends a document
that triage left out to be read.

## Mail (Gmail API)

`pipeline/regstudio/mailer.py` sends mail from the Mac through the Gmail API as the work account
(`REGSTUDIO_MAIL_FROM`, default mahak.mittal@joulewise.com), with the `gmail.send` scope only. One-time setup on the Mac:
`regstudio mail-setup --client ~/Downloads/credentials.json` (the Desktop OAuth client; it is copied to
`data/store/gmail_client.json` and the refresh token kept in `data/store/gmail_token.json`, both 0600 and never committed
or sent anywhere). Then `regstudio mail-test`.

- The sync job mails new project requests and chat contacts to `REGSTUDIO_MAIL_SALES` (sales@joulewise.com) about once a
  minute, Reply-To the visitor (sync ops `leads` / `leads_mailed`).
- `regstudio invite` emails the link when mail is set up (`--no-email` to only print it). The Admin page's "Email the
  invitation" queues a request (`rs_invite_requests`); the Mac makes the token itself and mails it, so the site never
  holds a usable link (ops `invite_requests` / `invite_requests_done`).
- After each scan, `regstudio mail-review` sends the waiting queue, by priority, to `REGSTUDIO_MAIL_REVIEW` (once a day).
- Every message is logged in `mail_log` under (kind, ref) and never sent twice; `regstudio mail-log` shows the last 20.
  Tests use `REGSTUDIO_MAIL=outbox`, which writes .eml files instead of sending. Never send real mail from tests.
- The subscriber newsletter (`send-digest`) stays on Resend; Gmail is not for bulk mail.

## Comments, memory and commercial illustrations

- **Comments.** On the review screen the legal team comments on a summary, headline, impact note, chart, illustration
  or edition. Stage `revise` answers open comments with a reply each and a proposed revision (a diff the reviewer
  accepts or rejects). Accepting changes the text but sends the summary back to `proposed`; it is never an approval.
- **Memory.** With a revision Claude may propose lessons: a style note, or a fact about the Indian power sector that
  must cite `{doc, pid}`. Stage `learn` proposes up to four cited facts per read document. Only lessons a reviewer
  approves (on `/memory`) are used: they are appended to every prompt sent to Claude (style always; facts by
  commission and topic) and written to `data/memory/house_notes.md`. Read that file before writing summaries here.
- **Commercial illustrations (beta).** `regstudio commercial <id>` or the review-screen button asks for one; stage
  `commercial` builds it. Every input cites a paragraph or is marked as an assumption with its reason; the steps are
  computed by `commercial.py` (+ - * / only) and the takeaway may quote numbers only through `{step}` slots. The
  jouleWise commercial team approves it separately; the public site shows only approved illustrations.

## Review priority

`priority.py` scores every order and draft out of 100 to order the review queue: stakeholder reach (40),
business opportunity for jouleWise and Urja Praxis (30), leads (20), urgency (10). It is computed by code from
kind, parties, significance, subjects and dates, shown with its reasons, and never published. Open drafts rank
highest, then orders with several parties. Tune the weights and subject lists in that file.

## Market impact and Studio comments

Both are opt-in per document (review screen button, or `regstudio run impact --doc <id>` /
`regstudio run comments --doc <id> --as <group>`), both are proposals until a reviewer approves, and
every statement cites paragraph ids of the document; uncited statements are dropped. Comment drafts
are also written as Markdown under `data/comments/<commission>/<doc>/<group>.md`.
