-- Simple charts for a summary (tariffs, capacities, timelines, trajectories), chosen from what the text contains.
-- NULL = not looked at yet; a JSON list (possibly empty) once the figures stage has run.
ALTER TABLE orders ADD COLUMN figures TEXT;
ALTER TABLE consultations ADD COLUMN figures TEXT;
ALTER TABLE regulations ADD COLUMN figures TEXT;
