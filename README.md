# Regulatory Studio

Weekly, legally reviewed summaries of Indian electricity regulatory orders, with an
interactive map tracing each order to the regulations, Act sections and earlier
decisions it rests on. Incubated by jouleWise.

Coverage: CERC, APTEL, UPERC, MERC, GERC, KERC, RERC, TNERC. Open access and tariff matters, plus draft regulations and consultations.

Architecture: https://claude.ai/artifact/E3uwohVAYcGw4XAJUgJUb4

## How it fits together

```
regstudio download         ->  data/inbox/<commission>/<YYYY-MM-DD>/<file>.pdf + .json
                                     |
Mac mini: pipeline/  intake -> extract -> registry -> triage -> read -> draft
                                     |            (working DB: data/store/working.db)
                         review   legal approves each summary and each link
                                     |
                         publish  -> data/snapshot/*.json  (approved only)
                                     |
Vercel:  web/   static pages, spider map, Markdown twins, llms.txt, feeds, API
```

Nothing unapproved ever reaches `data/snapshot/`. The site builds only from the snapshot.

The Mac mini is the server: it scans on Tuesday and Friday, serves the review screen to the legal team through a
Cloudflare Tunnel, and pushes approved items to the public site. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
and [docs/MAC_MINI_SERVER.md](docs/MAC_MINI_SERVER.md).

## Layout

| Path | What |
| --- | --- |
| `pipeline/regstudio/` | Python pipeline, one module per stage |
| `pipeline/prompts/` | Prompts given to Claude Code for triage, reading and drafting |
| `pipeline/schemas/` | JSON schemas: inbox metadata, model outputs |
| `pipeline/regstudio/review_app.py` | Local review app for the legal team (FastAPI); templates beside it |
| `web/` | Next.js site deployed on Vercel |
| `data/inbox/` | Where `regstudio download` (or the download team) drops files (git-ignored) |
| `data/store/` | Working database and extracted text (git-ignored) |
| `data/snapshot/` | Published, approved data the site builds from |

## Quick start on the Mac mini

```bash
cd ~/Downloads/regulatory-studio
python3 -m venv .venv && source .venv/bin/activate
pip install -e pipeline
regstudio init                 # create the working database
regstudio run intake extract   # pick up new files from data/inbox
regstudio run registry         # split regulations into clauses
regstudio run triage read draft --limit 20   # Claude Code stages
regstudio review               # review screen at http://127.0.0.1:8765
regstudio publish              # write approved items to data/snapshot
cd web && npm install && npm run build
```

`regstudio status` shows how many documents sit at each stage.
`regstudio send-digest` emails an approved digest through Resend. Full setup: `docs/FIRST_RUN_ON_MAC.md`.

## Claude Code on the Mac mini

Triage, read and draft call the `claude` CLI headless (`claude -p`) under the
jouleWise Claude subscription. They never run on Vercel.
Set `REGSTUDIO_READER=mock` to run without Claude (tests and demos).

See `CLAUDE.md` for the rules Claude Code follows in this repo.

## Sample data

`pipeline/tests/fixtures/` holds generated sample PDFs marked "SAMPLE - NOT A REAL ORDER".
They exist only to exercise the pipeline and site. Run `regstudio publish --clean`
before the first public deploy.
