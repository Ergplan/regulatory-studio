-- Pre-review checks on a proposed summary: an automatic number check and two independent AI reviewers.
-- JSON: {"numbers": {...}, "fact": {...}, "legal": {...}, "status": "clear" | "attention"}. NULL = not checked.
ALTER TABLE orders ADD COLUMN checks TEXT;
ALTER TABLE consultations ADD COLUMN checks TEXT;
