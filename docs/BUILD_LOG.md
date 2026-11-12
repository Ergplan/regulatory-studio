# Build log

Overnight build, 11–12 Nov 2026. Limits for unattended work: no public domain, no emails,
no downloads from commission sites, nothing deleted on the Mac.

| Time (IST) | Done |
| --- | --- |
| 11 Nov 21:20 | Backlog set: CI, inbox checker, review and publish tests, amendment assist, map polish, search and feeds, reviewer sign-in, Vercel deploy (blocked on GitHub app access) |
| 11 Nov 23:30 | Priority change from user: real orders for morning review. Fetched five CERC orders (13/SM, 16/SM 2026; 233/AT 2026; 779/MP, 979/MP 2025) and DSM Regulations 2024; paragraph merging for line-level PDFs; readable regulation ids and inferred clause headings; prepared-output reader mode; drafts written in chat and checked by the pipeline (0 references dropped); database copied to the Mac; docs/MORNING_REVIEW.md. APTEL 301 and 317 of 2026 not fetched (site certificate chain incomplete). |
| 11 Nov 22:10 | Vercel project created (root web, Next.js, team login protection on vercel.app); first deploy verified (noindex, empty). Added UPERC 2418 and 2416 of 2026 to the morning batch (2355 listed as interim); OCR now uses only installed Tesseract languages. RERC, MERC, GERC order PDFs not reachable via their sites. |
| 11 Nov 22:40 | check-inbox dry run; review and publish rule tests (14 tests); spider map redesign checked in headless Chrome (type inside boxes, readable regulation names, overflow); shorter order addresses; site search; RSS per commission and per topic; reviewers can set each order's public title. |
| 11 Nov 23:20 | Optional reviewer sign-in for office-network review; amendment stage: proposes substitute/insert/omit per clause, reviewer applies with effective date, old wording kept as history and shown on clause pages; migrations applied when the review screen starts. 17 tests. |

## Next for overnight check-ins (in order)

1. Extend the morning batch: state orders (UPERC 2408 and 2418 of 2026, RERC Shree Cement 04.11.2026, a MERC open access order) and the CERC Sharing Regulations 2020 and Trading Licence Regulations in the registry. Work on the Mac copy in ~/Downloads/regulatory-studio with REGSTUDIO_STORE=$HOME/rs-live/store, then copy working.db (journal_mode=DELETE) into data/store before 9 am.
2. Vercel project once GitHub access is granted.
3. Backlog: inbox checker, review/publish tests, map polish, search and feeds, reviewer sign-in, amendment assist.

## 11 Nov 2026 — commission downloaders

- `regstudio download` with adapters for CERC, UPERC, RERC (form postback), MERC (JSON feed),
  GERC (paged tables) and KERC (three order pages). APTEL stays on `ops/fetch_one.py`.
- Polite client: robots.txt, 3 s pause per host, retries; repairs incomplete TLS chains by
  fetching the named intermediate, with full verification kept.
- Parser tests on trimmed extracts of the live listing pages (24 tests pass).
- `ops/weeknight.sh` now downloads, checks the inbox, then runs the pipeline.
- 11 Nov, 17:50 UTC check-in: download report now shows orders on each page, newest date, and warns when a page yields no orders (layout change) or undated rows. Vercel deploys of today's commits all READY. 26 tests pass.
- 11 Nov, 19:50 UTC check-in: each real download saves its report (data/store/download_last.json); `regstudio status` and the review queue's new "Commission websites" table show newest order per site and any problems. 28 tests pass.
- 11 Nov, 21:50 UTC check-in: read the five downloaded RERC/GERC orders (file reader; all excerpts verified): Shree Cement (GEOA 200% limit), RUVITL 1,300 MW at ₹15.50, GUVNL solar ₹2.34 proposed; Waaree and Stockwell listed only. Extraction now repairs PDFs whose fi/fl ligatures come out as N/T (GERC's Cambria): 148 and 87 words fixed in two orders, none in clean ones. 29 tests pass.
- 12 Nov, early IST: review screen smoke-tested on the Mac with the real batch (queue and all 10 order pages load). Fixed RERC parser missing every other row (alternate rows use another class and button id). Added `regstudio fetch` (APTEL, MERC, regulations; polite client with TLS repair) and a RERC regulations adapter (`rerc-regs`, `--match`). 31 tests pass.
- 12 Nov, early IST: RERC GEOA Regulations, 2025 fetched (`rerc-regs --match`) and registered: 31 regulations found after three registry fixes (English version of bilingual gazettes, running heads merged into first paragraphs, regulations starting mid-paragraph). Review screen now pre-fills a suggested provision for unresolved links (abbreviation-aware: GEOA, DSM, GNA), which the reviewer confirms. Also downloaded RERC 2450/2026 (missed by the alternate-row bug). 37 tests pass.
- 12 Nov, 23:50 UTC check-in: review queue now leads with the case number and marks orders still carrying a long listing title ("needs a short title"). 38 tests pass.
- 12 Nov, 01:50 UTC check-in: smoke-tested the GEOA regulation page, suggested targets and queue flags on the Mac; morning review notes updated for ten orders, suggestions and the GEOA registry approval.
- 12 Nov, 03:50 UTC wrap-up: 38 pipeline tests pass, web build passes, everything pushed.
- 12 Nov, afternoon IST: draft regulations and consultations (CERC, GERC, KERC drafts; consult stage; review page; /consultations on the site). TNERC added as the eighth commission: case orders (CaseOrders.aspx) and draft regulations (ViewDR.aspx). 43 tests pass.
