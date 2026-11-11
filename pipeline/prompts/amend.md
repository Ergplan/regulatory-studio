You are reading an amendment to an Indian electricity regulation for Regulatory Studio's
clause registry. A reviewer checks every change you propose before it is applied.

Return:
- regulation_id: the id from the REGULATIONS list below of the principal regulation this
  amendment changes, or null if it is not listed. Never construct an id.
- effective_date: the date the amendment comes into force, as YYYY-MM-DD, or null if the
  text does not state it.
- changes: one entry per clause the amendment changes, in the principal regulation's numbering:
  - clause_number: e.g. "8" or "8(3)".
  - action: "substitute" (clause replaced), "insert" (new clause added) or "omit" (deleted).
    Treat a proviso or explanation added to a clause as a substitution of that clause with its
    full new wording if the amendment gives it; otherwise list it as "insert" with the added text.
  - new_text: the clause's new wording exactly as given in the amendment; null for "omit".
  - pid: the paragraph of the amendment where the change appears, e.g. "p2.4".
  - excerpt: a short passage copied word for word from that paragraph (under 300 characters).

Return ONLY a JSON object matching this schema, with no other text:
{schema}

Commission: {commission}
Document title as listed: {title}

REGULATIONS (ids you may use):
{regulations}

AMENDMENT TEXT (each paragraph starts with its id in brackets):
{text}
