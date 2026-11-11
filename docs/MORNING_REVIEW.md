# Morning review, 12 Nov 2026: first real batch

Seven orders from the last six weeks (five CERC, two UPERC) are waiting in the review screen. Each has a draft
summary and proposed links, every link tied to a paragraph of the order. Nothing is published
until it is approved here.

## Open the review screen (Mac mini, Terminal)

```bash
cd ~/Downloads/regulatory-studio
python3 -m venv .venv && source .venv/bin/activate   # first time only
pip install -e pipeline                               # first time only
regstudio review
```

Then open http://127.0.0.1:8765, enter your name once, and work down the queue.

## The batch

| Order | Date | What it decides | Check especially |
| --- | --- | --- | --- |
| 979/MP/2025, Vena Energy | 02.11.2026 | Blended wind project (81% wind) stays in the hybrid deviation band; Regulations 11 and 12 cannot create a new generator category | Two separate links to Regulations 11 and 12 from one sentence |
| 16/SM/2026 (suo motu) | 03.10.2026 | Reserve-shortfall recovery of DAS Pool deficits deferred to 05.04.2027 | Link type "relaxes" for a removal-of-difficulty deferral |
| 13/SM/2026 (suo motu) | 28.10.2026 | Proposal only: pumped storage in HP-DAM; comments within 15 days | Summary must read as a proposal, not a decision |
| 233/AT/2026, SJVN | 26.10.2026 | FDRE tariffs ₹4.82–4.91/kWh adopted for 448 MW, subject to PPAs and PSAs | The order cites the comparison case as both 772/AT/2025 and 722/AT/2025 |
| 779/MP/2025, Mounting Renewable / Welspun | 26.10.2026 | SCOD extended to 30.06.2026; ISTS waiver only for capacity commissioned by then | Waiver limited to the 174.9 MW reported as commissioned |
| UPERC 2418 of 2026, NPCL | 27.10.2026 | 300 MW FDRE (RTC) procurement approved; whole capacity may go to one L1 bidder; only final-connectivity holders may bid | Scanned order (OCR). Para 25 refers to "changes at Para 24" but the changes are in Para 23 |
| UPERC 2416 of 2026, NIDP | 14.10.2026 | Short-term RTC bagasse power adopted at ₹5.12 (5 MW) and ₹5.10 (3 MW); exchange purchases allowed at 2 paise margin | Scanned order (OCR); the signature date is unreadable, date taken from UPERC's listing |
| RERC 2416/2026, Shree Cement v. JVVNL | 04.11.2026 | Dismissed: an existing behind-the-meter captive plant cannot halve contract demand to use the 200% GEOA limit; it must migrate to GEOA under Regulation 7 and add capacity | Links to the GEOA clauses stay unresolved until the GEOA Regulations, 2025 are in the registry. RERC also records non-disclosure by the petitioner |
| RERC 2451/2026, RUVITL | 29.10.2026 | Up to 1,300 MW from GoHP via PTC at ₹15.50/kWh (landed ~₹16.62) approved for Nov 2026–Feb 2027, as an exception, cost subject to true-up prudence check | Check the reading of Regulation 77(6)/(7) and the ₹4.59/kWh ceiling; "not a precedent" should stay in the summary |
| GERC 2695/2026, GUVNL solar Phase XXVIII | 07.11.2026 | ₹2.34/kWh adopted for 1,250 MW: Welspun 300, NLC India Renewables 900, Meghmani 50 | The order's allocation table is garbled in the PDF text; capacities taken from para 7.34. The PDF's "fi" ligature extracts as "N" (e.g. "Niled"), so quotes avoid those words |

Also listed without a summary: UPERC 2355 of 2026 (Fourth Partner Energy, storage at commissioned
RE plants), an interim hearing order; next hearing 17.11.2026. GERC 2706/2026 (Waaree v. GETCO:
consent-based interim use of an idle 66 kV bay until 25.11.2027, merits left open) and GERC IA
85/2026 in 2749/2026 (Stockwell BESS: bank guarantee and termination, out of scope).

## How to treat links

- **Resolved links** point to a clause in the registry or an Electricity Act section. Approve,
  change the type, or reject.
- **Unresolved links** (shown in red) cite regulations not yet in the registry: Sharing
  Regulations 2020, Trading Licence Regulations, Conduct of Business Regulations 2023, and
  earlier orders. Reject them for now or leave them open; they cannot be approved without a target.
- **Registry**: the DSM Regulations, 2024 have been split into 50 clauses. Please approve them
  (one button on the regulation page) so the four DSM links can be published.

## After review

`regstudio publish` writes only approved items for the website. Nothing is emailed or
put online until the domain and Vercel are set up.

## How this batch was made

- The orders were fetched from cercind.gov.in with `ops/fetch_one.py`, a stopgap until the
  download script is ready.
- The `claude` CLI could not run in the chat's shell, so Claude read the orders in the chat
  session and saved its drafts to `data/reader_outputs/`. The pipeline then ran its usual checks
  (`REGSTUDIO_READER=file`): every paragraph id exists and every quoted excerpt matches the
  order text. From the weeknight runs onward, Claude Code on the Mac does this step.
- UPERC orders are scanned; their text came from OCR, so check quotes against the PDF.
- The RERC and GERC orders were fetched on 11 Nov by `regstudio download` and read the same way.
  MERC is not fetched (its robots.txt disallows bots); KERC has listed nothing since 31 Aug.
- The APTEL judgment in Appeal Nos. 301 and 317 of 2026 could not be fetched, because the
  APTEL site's certificate chain is incomplete.
