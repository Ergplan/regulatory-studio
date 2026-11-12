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
| Mon–Fri nights | `ops/weeknight.sh` (downloads, then the pipeline) | Automatic |
| Saturday | Review queue: summaries, links, registry, digest | Legal team |
| Sunday | `regstudio publish`, commit `data/snapshot`, push (Vercel deploys), `send-digest` | You |

## Downloading orders

```bash
regstudio download --dry-run                    # list what would be fetched (last 14 days)
regstudio download --since 2026-10-01 --limit 20
regstudio download --commission gerc --commission kerc
regstudio download --commission rerc-regs --since 2025-07-01 --match "Green Energy Open Access"
regstudio fetch https://example/judgment.pdf aptel judgment --date 2026-11-05 --case "Appeal No. 301 of 2026"
```

| Commission | Source | Notes |
| --- | --- | --- |
| CERC | recent_orders.html | table of petitions |
| UPERC | Order_Users.aspx | "Order dated ..." links |
| RERC | office-orders page | PDFs come back through a form postback |
| MERC | site's order data feed (JSON) | **Skipped:** merc.gov.in's robots.txt asks all automated clients to stay out, and the script obeys. Save MERC orders from the site in your browser, then add each with `regstudio fetch ~/Downloads/<file>.pdf merc order --source-url <its address> --date ... --case ...`, or ask MERC to allow automated access |
| GERC | judgement orders + RE orders, paged | |
| KERC | miscellaneous, generic tariff and tariff order pages | |
| RERC regulations (`rerc-regs`) | regulations page | new regulations and amendments; `--match` picks one by title |
| CERC drafts (`cerc-drafts`) | Draft_reg.html | draft regulations and proposals, with the comment deadline and hearing date |
| GERC drafts (`gerc-drafts`) | draft regulations page | GERC lists no deadline: enter it from the public notice on the review screen |
| KERC drafts (`kerc-drafts`) | draft regulations page | issue date and last date for suggestions |
| TNERC (`tnerc`) | CaseOrders.aspx | case orders with petitioner, respondent and order date |
| TNERC drafts (`tnerc-drafts`) | ViewDR.aspx | draft regulations with last date; the link is TNERC's public notice with the draft |
| APTEL | no listing the script can read | add with `regstudio fetch <url> aptel judgment --date ... --case ...` |

Each file lands in `data/inbox/<commission>/<today>/` with its metadata JSON. Already-fetched
items are remembered in `data/store/download_seen.json`. Some state sites send an incomplete
certificate chain; the script fetches the missing intermediate certificate from the address the
site's own certificate names (never a root) and still checks the full chain against the Mac's
trusted roots. The script reads each site's robots.txt and skips anything it disallows.
Anything that is not a PDF (an error page, say) is skipped and reported.

## Draft regulations and consultations

Drafts are fetched while their comment deadline or hearing is still ahead (or if issued in the last
14 days). `regstudio run consult` drafts a plain-English summary, the main proposed changes and the
deadline; they appear under "Draft regulations and consultations" on the review screen. Check the
deadline against the public notice, then approve. Approved drafts are published on /consultations,
with the days left to comment. MERC and UPERC drafts are added by hand:
`regstudio fetch <pdf or url> merc draft --date YYYY-MM-DD --title "..."`, then set the deadline on
the review screen.

## For the download team

Before handing files over, run `regstudio check-inbox`. It lists every PDF whose metadata is
missing or invalid, whose hash does not match, or that sits in the wrong folder, and registers
nothing. It exits with status 1 if anything needs fixing, so it can gate the download script.

## Reviewers on other machines

By default the review screen listens only on the Mac itself (127.0.0.1). To let the legal team
review from their own laptops on the office network:

```bash
regstudio add-reviewer "Full Name"        # once per reviewer; asks for a password (10+ characters)
regstudio review --host 0.0.0.0           # then open http://<mac-mini-ip>:8765 from another machine
```

Once any reviewer is added, every page needs sign-in and each approval is recorded under the
signed-in name. Passwords are stored as salted hashes in `data/store/reviewers.json`, never in git.
The screen is plain HTTP, so use it only on the office network, not over the internet.
