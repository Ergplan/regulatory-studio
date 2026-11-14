-- The legal team's comments, the revisions Claude proposes in reply, and what the studio learns from both.

CREATE TABLE IF NOT EXISTS review_comments (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id      TEXT,                 -- the document commented on (NULL for a comment on an edition)
  digest_id   TEXT,                 -- the edition commented on, if any
  target      TEXT NOT NULL,        -- summary | headline | impact | figures | commercial | edition | other
  quote       TEXT,                 -- the words the comment is about, if the reviewer gave them
  body        TEXT NOT NULL,
  author      TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'open',   -- open | answered (a revision is proposed) | resolved | dismissed
  reply       TEXT,                 -- Claude's reply, proposed with the revision
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_by TEXT,
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_comments_doc ON review_comments(doc_id, status);

CREATE TABLE IF NOT EXISTS revisions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id      TEXT NOT NULL,
  fields      TEXT NOT NULL,        -- JSON {headline?, issue?, outcome?, summary?}: only what changes
  comment_ids TEXT NOT NULL,        -- JSON list of the comments it answers
  status      TEXT NOT NULL DEFAULT 'proposed',  -- proposed | accepted | rejected
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  decided_by  TEXT,
  decided_at  TEXT
);

-- What the studio has learnt. A style note is how the legal team wants things written; a fact is something
-- true about the Indian power sector, cited to a paragraph. Only approved notes are used in prompts.
CREATE TABLE IF NOT EXISTS lessons (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kind        TEXT NOT NULL,        -- style | fact
  text        TEXT NOT NULL,
  scope       TEXT NOT NULL DEFAULT 'all',   -- all | a commission code | a topic slug
  doc_id      TEXT,                 -- source of a fact
  pid         TEXT,
  comment_id  INTEGER,              -- the comment it was learnt from
  status      TEXT NOT NULL DEFAULT 'proposed',  -- proposed | approved | retired
  added_by    TEXT NOT NULL,        -- 'model' or the reviewer's name
  approved_by TEXT,
  approved_at TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status, kind);

-- Which documents the learn stage has already mined for facts.
ALTER TABLE documents ADD COLUMN learnt_at TEXT;

-- Commercial illustrations (beta): worked examples with cited inputs and flagged assumptions; the arithmetic
-- is done by code. Reviewed by the commercial team separately from the legal summary.
ALTER TABLE orders ADD COLUMN commercial TEXT;
ALTER TABLE orders ADD COLUMN commercial_status TEXT;     -- requested | proposed | approved | rejected
ALTER TABLE orders ADD COLUMN commercial_by TEXT;
ALTER TABLE consultations ADD COLUMN commercial TEXT;
ALTER TABLE consultations ADD COLUMN commercial_status TEXT;
ALTER TABLE consultations ADD COLUMN commercial_by TEXT;
