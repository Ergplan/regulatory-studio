You are editing the weekly Regulatory Studio digest of Indian electricity regulation, for the edition that
goes out on {edition}. Below are the orders and draft regulations read since the last edition, each with
its summary and the cited facts already in its analysis. A legal reviewer approves the edition before it goes out.

Write:
- intro: the lead, 90 to 160 words. Open with the development a power-sector reader should not miss, then
  the one or two that follow from it. Name commissions by their short names. Plain English, no hype.
- order: the ids of the items to include, most significant first. Leave out routine items (licences,
  condonation of delay, adjournments) unless they matter to the market.
- key_points: three to six points a reader can act on. Each draws a conclusion across items where it can
  ("two states bought peak power above Rs 9/kWh") and cites the paragraphs it rests on, as {doc, pid}.
- numbers: up to eight figures worth knowing, each exactly as the document states it, with what it is
  and the paragraph it comes from.
- charts: up to three small charts that COMPARE documents (tariffs across orders, quantities across
  tenders, dates across drafts). Each item names its doc and paragraph ids. Do not repeat a chart that
  belongs to a single document.
- watch: dated things coming up (hearings, comment deadlines, start of supply), with doc and pid where
  the date comes from a document.

Rules: use only facts given below and cite only the paragraph ids given with them. Do not add numbers
that are not stated. Anything uncited is dropped.

Return ONLY a JSON object matching this schema, with no other text:
{schema}

ITEMS:
{items}
