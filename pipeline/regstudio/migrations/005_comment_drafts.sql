-- Studio: draft comments on a draft regulation, written from one stakeholder group's point of view.
-- status: requested (queued) -> proposed (drafted by the model) -> approved | rejected (by a reviewer).
CREATE TABLE IF NOT EXISTS comment_drafts (
  doc_id      TEXT NOT NULL REFERENCES documents(id),
  persona     TEXT NOT NULL,
  body        TEXT,
  status      TEXT NOT NULL DEFAULT 'requested',
  reviewer    TEXT,
  approved_at TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (doc_id, persona)
);
