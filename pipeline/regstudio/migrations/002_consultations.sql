-- Draft regulations, consultation papers and suo motu proposals open for public comment.

CREATE TABLE IF NOT EXISTS consultations (
  doc_id            TEXT PRIMARY KEY REFERENCES documents(id),
  kind              TEXT NOT NULL DEFAULT 'draft_regulation', -- draft_regulation | draft_amendment | consultation_paper | proposal
  issued_date       TEXT,
  comment_deadline  TEXT,          -- last date for comments, as the commission states it
  hearing_date      TEXT,
  related           TEXT,          -- JSON [{label, url}]: public notice, explanatory memorandum, ...
  summary           TEXT,          -- what it proposes, in plain words
  proposes          TEXT,          -- JSON list of the main changes
  amends            TEXT,          -- the regulation it would change, as written
  summary_status    TEXT NOT NULL DEFAULT 'none',  -- none | proposed | approved | rejected
  reviewer          TEXT,
  approved_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_consult_deadline ON consultations(comment_deadline);
