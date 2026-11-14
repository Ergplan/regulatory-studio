-- The weekly digest becomes an edition: a lead, key points, numbers to know, charts across documents and
-- dates to watch, each citing a paragraph of a document in the edition. Items may be orders or drafts.
ALTER TABLE digests ADD COLUMN edition_date TEXT;   -- the Friday it goes out
ALTER TABLE digests ADD COLUMN key_points TEXT;     -- JSON [{text, items[], basis[{doc, pid}]}]
ALTER TABLE digests ADD COLUMN numbers TEXT;        -- JSON [{value, label, doc, pid}]
ALTER TABLE digests ADD COLUMN charts TEXT;         -- JSON [{type, title, unit?, note?, items[{label, value|start,end, tag?, context?, doc, basis[]}]}]
ALTER TABLE digests ADD COLUMN watch TEXT;          -- JSON [{date, text, doc?, pid?}]
