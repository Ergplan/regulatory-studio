-- Regulatory Studio working database (SQLite). Everything the model writes is 'proposed'.

CREATE TABLE IF NOT EXISTS documents (
  id            TEXT PRIMARY KEY,          -- sha256 of the PDF
  commission    TEXT NOT NULL,
  doc_type      TEXT NOT NULL,             -- order | judgment | regulation | amendment
  source_url    TEXT NOT NULL,
  downloaded_at TEXT NOT NULL,
  title         TEXT,
  doc_date      TEXT,
  case_number   TEXT,
  file_path     TEXT NOT NULL,             -- relative to data/store, e.g. files/<sha>.pdf
  page_count    INTEGER,
  ocr           INTEGER DEFAULT 0,         -- 1 if any page needed OCR
  language      TEXT,
  stage         TEXT NOT NULL DEFAULT 'new',
  -- stages: new -> extracted -> registered (regulations)
  --         new -> extracted -> triaged -> read -> drafted (orders, judgments)
  --         'listed' = triaged below threshold; 'error' = needs a look
  error         TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_documents_stage ON documents(stage);

CREATE TABLE IF NOT EXISTS paragraphs (
  doc_id  TEXT NOT NULL REFERENCES documents(id),
  pid     TEXT NOT NULL,                   -- 'p3.12' = page 3, paragraph 12
  page    INTEGER NOT NULL,
  idx     INTEGER NOT NULL,
  text    TEXT NOT NULL,
  bbox    TEXT,                            -- JSON [x0,y0,x1,y1] for jumping the PDF viewer
  PRIMARY KEY (doc_id, pid)
);

CREATE TABLE IF NOT EXISTS act_sections (
  id      TEXT PRIMARY KEY,                -- 'ea2003/s42'
  act     TEXT NOT NULL,
  number  TEXT NOT NULL,
  title   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regulations (
  id             TEXT PRIMARY KEY,         -- 'uperc/green-energy-oa-2024'
  commission     TEXT NOT NULL,
  title          TEXT NOT NULL,
  short_title    TEXT,
  notified_date  TEXT,
  doc_id         TEXT REFERENCES documents(id),
  made_under     TEXT,                     -- JSON list of act_section ids
  status         TEXT NOT NULL DEFAULT 'proposed',
  reviewer       TEXT,
  approved_at    TEXT
);

CREATE TABLE IF NOT EXISTS clauses (
  id             TEXT PRIMARY KEY,         -- 'uperc/green-energy-oa-2024/8(2)'
  regulation_id  TEXT NOT NULL REFERENCES regulations(id),
  number         TEXT NOT NULL,            -- '8(2)'
  heading        TEXT,
  text           TEXT NOT NULL,
  in_force_from  TEXT,
  in_force_to    TEXT,                     -- null = in force
  amended_by     TEXT REFERENCES documents(id),
  source_pid     TEXT,
  status         TEXT NOT NULL DEFAULT 'proposed',
  reviewer       TEXT,
  approved_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_clauses_reg ON clauses(regulation_id);

CREATE TABLE IF NOT EXISTS orders (
  doc_id           TEXT PRIMARY KEY REFERENCES documents(id),
  topics           TEXT,                   -- JSON list of topic slugs
  significance     INTEGER,                -- 1..5
  triage_reason    TEXT,
  parties          TEXT,                   -- JSON list of {name, role}
  issue            TEXT,
  outcome          TEXT,
  summary          TEXT,
  summary_status   TEXT NOT NULL DEFAULT 'none',  -- none | proposed | approved | rejected
  reviewer         TEXT,
  approved_at      TEXT,
  revised_at       TEXT
);

CREATE TABLE IF NOT EXISTS links (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  from_doc       TEXT NOT NULL REFERENCES documents(id),
  link_type      TEXT NOT NULL,
  target_kind    TEXT NOT NULL,            -- clause | regulation | act_section | document
  target_id      TEXT,                     -- null when unresolved
  citation_text  TEXT NOT NULL,            -- as written in the order
  resolved       INTEGER NOT NULL DEFAULT 0,
  pid            TEXT NOT NULL,            -- paragraph the link rests on
  excerpt        TEXT NOT NULL,
  added_by       TEXT NOT NULL DEFAULT 'model',  -- model | reviewer
  status         TEXT NOT NULL DEFAULT 'proposed', -- proposed | approved | rejected
  reviewer       TEXT,
  approved_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_doc);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id);

CREATE TABLE IF NOT EXISTS digests (
  id           TEXT PRIMARY KEY,           -- ISO week, '2026-W46'
  from_date    TEXT NOT NULL,
  to_date      TEXT NOT NULL,
  intro        TEXT,
  items        TEXT,                       -- JSON list of doc_ids in display order
  status       TEXT NOT NULL DEFAULT 'proposed',
  reviewer     TEXT,
  approved_at  TEXT,
  published_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  stage     TEXT NOT NULL,
  started   TEXT NOT NULL DEFAULT (datetime('now')),
  finished  TEXT,
  ok        INTEGER DEFAULT 0,
  failed    INTEGER DEFAULT 0,
  note      TEXT
);

CREATE TABLE IF NOT EXISTS audit (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  at        TEXT NOT NULL DEFAULT (datetime('now')),
  actor     TEXT NOT NULL,                 -- reviewer name or 'pipeline'
  action    TEXT NOT NULL,
  object    TEXT NOT NULL,
  detail    TEXT
);
