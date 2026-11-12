You choose small charts for the summary of an Indian electricity regulatory {kind}. A chart is worth
adding only when it lets a reader see something faster than the sentence does. Many documents need none:
return an empty list rather than a weak chart.

Commission: {commission}
Title: {title}
Summary (already drafted): {summary}

Choose by what the text contains:
- bars: two to eight figures in the SAME unit that a reader would compare (tariffs discovered, capacity
  by bidder, a rate against its ceiling, a limit before and after). Never one number. Never mix units
  in one chart: Rs/kWh and MW are two charts. Use `tag` when the figures are of different kinds (adopted,
  not adopted, ceiling, a party's claim) and `context: true` for those shown only for comparison.
- series: one quantity at three or more ordered points (a trajectory by year, a schedule of steps).
- timeline: two or more dated periods or events (supply period, comment deadline, a cut-off, the date a
  rule starts or stops). Use ISO dates; a single day has `start` only.

Rules:
1. Every item cites the paragraph ids it is read from (e.g. "p4.2"). Items without a valid citation are
   discarded, and a chart left with too few items is dropped.
2. Use the figures exactly as the text gives them. Do not compute, convert, average or estimate.
3. A figure that is a party's claim and not the Commission's finding must say so in `tag` or `note`.
4. At most three charts, most useful first. Titles say what is shown, not what to conclude.

Return only JSON matching this schema:
{schema}

Text:
{text}
