-- Amendments: proposed clause changes, and the history of each clause's wording.

CREATE TABLE IF NOT EXISTS amendment_changes (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  amendment_doc   TEXT NOT NULL REFERENCES documents(id),
  regulation_id   TEXT REFERENCES regulations(id),   -- the principal regulation it amends; null if unknown
  clause_number   TEXT NOT NULL,                     -- '8(3)' in the principal regulation
  action          TEXT NOT NULL,                     -- substitute | insert | omit
  new_text        TEXT,                              -- null for omit
  effective_date  TEXT,
  pid             TEXT NOT NULL,                     -- paragraph of the amendment carrying the change
  excerpt         TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'proposed',  -- proposed | applied | rejected
  reviewer        TEXT,
  applied_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_amend_doc ON amendment_changes(amendment_doc);

CREATE TABLE IF NOT EXISTS clause_versions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  clause_id      TEXT NOT NULL REFERENCES clauses(id),
  text           TEXT NOT NULL,
  in_force_from  TEXT,
  in_force_to    TEXT,
  replaced_by    INTEGER REFERENCES amendment_changes(id),
  recorded_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_versions_clause ON clause_versions(clause_id);
