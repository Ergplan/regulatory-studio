-- Mail the studio Mac sends through Gmail (mailer.py). One row per (kind, ref): a message is never sent twice.
CREATE TABLE IF NOT EXISTS mail_log (
  kind     TEXT NOT NULL,              -- lead | chat | invite | review | test
  ref      TEXT NOT NULL,              -- lead id, chat id, invitation, day
  to_addr  TEXT NOT NULL,
  subject  TEXT NOT NULL,
  status   TEXT NOT NULL,              -- sent | written (outbox mode) | failed
  gmail_id TEXT,
  error    TEXT,
  at       TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (kind, ref)
);
