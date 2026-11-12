You are reading a draft regulation, draft amendment, consultation paper or suo motu proposal
published by {commission} for public comment. Title as listed: {title}

Write for a busy reader in the Indian power sector who must decide whether to comment.

- kind: draft_regulation (new regulations), draft_amendment (changes to existing regulations),
  consultation_paper, or proposal (a suo motu proposal or approach paper).
- summary: what is proposed and who it affects, in plain words, at most 1,500 characters. Say it is
  a proposal; do not describe it as decided.
- proposes: up to eight main changes, one short line each, with numbers where the draft gives them.
- comment_deadline and hearing_date: only if the text states them (YYYY-MM-DD); otherwise null.
  Do not calculate a date from "within 30 days of publication".
- amends: the principal regulation it would change, as named in the draft; null for new regulations.

Return only JSON matching this schema:
{schema}

Text, paragraph by paragraph:
{text}
