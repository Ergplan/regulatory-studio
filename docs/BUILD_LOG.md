# Build log

Overnight build, 11–12 Nov 2026. Limits for unattended work: no public domain, no emails,
no downloads from commission sites, nothing deleted on the Mac.

| Time (IST) | Done |
| --- | --- |
| 11 Nov 21:20 | Backlog set: CI, inbox checker, review and publish tests, amendment assist, map polish, search and feeds, reviewer sign-in, Vercel deploy (blocked on GitHub app access) |
| 11 Nov 23:30 | Priority change from user: real orders for morning review. Fetched five CERC orders (13/SM, 16/SM 2026; 233/AT 2026; 779/MP, 979/MP 2025) and DSM Regulations 2024; paragraph merging for line-level PDFs; readable regulation ids and inferred clause headings; prepared-output reader mode; drafts written in chat and checked by the pipeline (0 references dropped); database copied to the Mac; docs/MORNING_REVIEW.md. APTEL 301 and 317 of 2026 not fetched (site certificate chain incomplete). |
| 11 Nov 22:10 | Vercel project created (root web, Next.js, team login protection on vercel.app); first deploy verified (noindex, empty). Added UPERC 2418 and 2416 of 2026 to the morning batch (2355 listed as interim); OCR now uses only installed Tesseract languages. RERC, MERC, GERC order PDFs not reachable via their sites. |
| 11 Nov 22:40 | check-inbox dry run; review and publish rule tests (14 tests); spider map redesign checked in headless Chrome (type inside boxes, readable regulation names, overflow); shorter order addresses; site search; RSS per commission and per topic; reviewers can set each order's public title. |

## Next for overnight check-ins (in order)

1. Extend the morning batch: state orders (UPERC 2408 and 2418 of 2026, RERC Shree Cement 04.11.2026, a MERC open access order) and the CERC Sharing Regulations 2020 and Trading Licence Regulations in the registry. Work on the Mac copy in ~/Downloads/regulatory-studio with REGSTUDIO_STORE=$HOME/rs-live/store, then copy working.db (journal_mode=DELETE) into data/store before 9 am.
2. Vercel project once GitHub access is granted.
3. Backlog: inbox checker, review/publish tests, map polish, search and feeds, reviewer sign-in, amendment assist.
