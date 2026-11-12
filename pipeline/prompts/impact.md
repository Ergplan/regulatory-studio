You assess the market impact of an Indian electricity regulatory {kind} for a commercial reader
(a C&I buyer, developer, discom planner or trader) who wants to know what it changes for them.

Commission: {commission}
Title: {title}
Summary (already drafted): {summary}

Using the text below, return:
- market_note: one or two sentences on what changes in the market and for whom.
- key_points: up to five insights a commercial reader would act on (costs and prices with numbers,
  deadlines, eligibility, obligations, precedent value). No restating of the summary.
- procurement: procurement requirements created or changed (RPO or storage obligations, quantities,
  bidding rules, approvals needed, contract terms). Empty list if none.
- stakeholders: for each group, level 0 (no effect) to 3 (direct, material), effect
  (opportunity, cost, mixed, neutral) and a one-line why. Groups: discoms, ci_consumers
  (open access and C&I consumers), captive, re_developers, storage, conventional (thermal and hydro
  generators), transmission (transmission licensees, SLDC/RLDC), traders (traders and exchanges).
  Rate only what the text supports; a proposal affects people only if adopted, so say "if adopted".

Return only JSON matching this schema:
{schema}

Text:
{text}
