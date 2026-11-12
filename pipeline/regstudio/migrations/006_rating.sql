-- Overall impact rating, set only by a reviewer on the review screen (never by the model): high, medium, low or NULL.
ALTER TABLE orders ADD COLUMN rating TEXT;
ALTER TABLE consultations ADD COLUMN rating TEXT;
ALTER TABLE regulations ADD COLUMN rating TEXT;
