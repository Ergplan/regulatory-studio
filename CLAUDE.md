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

## Scheduled runs (week 4)

Weeknights, one stage per run, with `--limit` so each run stays modest:

```
regstudio download --limit 40
regstudio run intake extract registry amend
regstudio run consult --limit 10
regstudio run triage --limit 60
regstudio run read --limit 15
regstudio run draft
```

A run that hits a usage limit stops cleanly; the next run resumes from DB state.
