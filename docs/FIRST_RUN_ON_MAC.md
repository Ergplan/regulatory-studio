# First run on the Mac mini (macOS Terminal)

Run these in the Mac's own Terminal, not inside a Claude chat shell: the Claude stages
need the `claude` CLI signed in to the jouleWise subscription.

```bash
cd ~/Downloads/regulatory-studio
git init -b main && git add -A && git commit -m "Regulatory Studio scaffold"
python3 -m venv .venv && source .venv/bin/activate
pip install -e "pipeline[test]"
pytest pipeline/tests                      # 5 tests, mock reader

# Try the whole flow on the SAMPLE PDFs
python3 pipeline/tests/make_fixtures.py data/inbox
regstudio run intake extract registry
REGSTUDIO_READER=mock regstudio run triage read draft
regstudio review                           # http://127.0.0.1:8765

# First real Claude call (checks the CLI and subscription work headless)
echo 'Reply with only {"ok": true}' | claude -p --output-format json
```

If the last command prints JSON with `"result"`, the triage, read and draft stages will work
without `REGSTUDIO_READER=mock`. If your CLI rejects `--output-format`, tell Claude and the
runner will be switched to plain-text mode.

## Site

```bash
cd web && npm install && npm run dev       # http://localhost:3000, reads ../data/snapshot
```

Run `regstudio publish` first so `data/snapshot` has content. Before the first public deploy,
run `regstudio publish --clean` to drop the SAMPLE items.

## Vercel

Project root directory: `web`. Environment: `NEXT_PUBLIC_SITE_URL` = the final domain.
`data/snapshot` must be committed; Vercel reads it at build time.

## Weekly email (Resend)

1. In Resend: verify your sending domain, create a segment for digest subscribers, create an API key.
2. In Vercel (project settings, environment variables): `RESEND_API_KEY`, `RESEND_SEGMENT_ID`,
   `RESEND_FROM` (e.g. `Regulatory Studio <digest@your-domain>`), `SUBSCRIBE_SECRET` (long random
   string), `NEXT_PUBLIC_SITE_URL`. See `web/.env.example`.
3. On the Mac, put the same three Resend values plus `REGSTUDIO_SITE_URL` in your shell profile.

Sign-up is double opt-in: the site emails a signed confirmation link; the contact is added to the
Resend segment only after it is clicked. Nothing is stored before that.

After the legal team approves a digest and you publish and deploy:

```bash
regstudio send-digest            # creates a DRAFT broadcast in Resend to check
regstudio send-digest --send     # sends it to all confirmed subscribers
```

## Weeknight schedule

`ops/weeknight.sh` runs intake to reading each weeknight at 23:30 and drafts the digest on Fridays.
To install it, edit `REPO_PATH` in `ops/in.jouleWise.regulatorystudio.plist`, then:

```bash
cp ops/in.jouleWise.regulatorystudio.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/in.jouleWise.regulatorystudio.plist
```

## Scanned orders

`brew install tesseract tesseract-lang` lets extraction OCR scanned pages in English and Hindi.
OCR'd orders are flagged in the review queue for a closer check.

## Weekly rhythm

| When | What | Who |
| --- | --- | --- |
| Mon–Fri nights | Download script, then `ops/weeknight.sh` | Automatic |
| Saturday | Review queue: summaries, links, registry, digest | Legal team |
| Sunday | `regstudio publish`, commit `data/snapshot`, push (Vercel deploys), `send-digest` | You |

## For the download team

Before handing files over, run `regstudio check-inbox`. It lists every PDF whose metadata is
missing or invalid, whose hash does not match, or that sits in the wrong folder, and registers
nothing. It exits with status 1 if anything needs fixing, so it can gate the download script.
