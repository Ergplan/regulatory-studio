-- A plain-English headline for every summarised order, proposed with the summary and edited by the reviewer.
-- The commission's own title stays in documents.title and is shown beneath it.
ALTER TABLE orders ADD COLUMN headline TEXT;
