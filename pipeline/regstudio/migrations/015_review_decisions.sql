-- Every review decision, with the reviewer's rank (hierarchy.py). Rows are only ever added.
CREATE TABLE IF NOT EXISTS review_decisions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  at              TEXT NOT NULL DEFAULT (datetime('now')),
  kind            TEXT NOT NULL,        -- order | consultation | digest | link | clause | regulation | amendment_change | comment_draft | lesson | impact | figures | rating
  object          TEXT NOT NULL,        -- the item's id
  action          TEXT NOT NULL,        -- approve | reject | reopen | save | accept | ...
  reviewer        TEXT NOT NULL,
  email           TEXT,                 -- the verified sign-in email, when there is one
  rank            INTEGER NOT NULL,     -- 2 senior reviewer, 1 reviewer
  status_before   TEXT,
  status_after    TEXT,
  reviewer_before TEXT,
  text_before     TEXT,                 -- JSON: the item's text before this decision
  text_after      TEXT,                 -- JSON: and after it
  overrides       INTEGER REFERENCES review_decisions(id),   -- the other reviewer's decision this one replaced
  refused         INTEGER NOT NULL DEFAULT 0,                -- 1: an attempt to change a senior reviewer's decision, not applied
  note            TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_item ON review_decisions(kind, object, id);
