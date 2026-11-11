You are triaging an Indian electricity regulatory order for Regulatory Studio, a weekly
digest read by power-sector professionals. Read the order text below and decide:

- in_scope: true only if the order concerns open access (including green energy open access,
  banking, wheeling, cross-subsidy surcharge, additional surcharge) or tariff matters
  (retail, generation or transmission tariff, ARR and true-up, tariff adoption, PPA approval).
- topics: up to 5 slugs, chosen ONLY from this list: {topics}
- significance, 1 to 5:
  1 routine and individual (time extension, adjournment, withdrawal, simple compliance)
  2 individual dispute with no wider effect
  3 settles a point that affects a class of consumers or generators
  4 interprets or relaxes a regulation, or departs from earlier orders
  5 sector-wide effect (new methodology, tariff for a whole state, regulation struck down)
- reason: one or two plain sentences explaining the score.

Base everything on the text. Do not use outside knowledge about these parties.

Return ONLY a JSON object matching this schema, with no other text:
{schema}

Commission: {commission}
Document title as listed: {title}

ORDER TEXT (each paragraph starts with its id in brackets):
{text}
