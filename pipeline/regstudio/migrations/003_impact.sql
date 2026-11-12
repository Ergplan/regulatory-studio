-- Market impact assessment (proposed with the summary, approved with it).
ALTER TABLE orders ADD COLUMN impact TEXT;
ALTER TABLE consultations ADD COLUMN impact TEXT;
