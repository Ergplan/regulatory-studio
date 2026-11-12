-- Market impact for notified regulations too. NULL = not assessed; 'requested' = queued for the impact stage.
ALTER TABLE regulations ADD COLUMN impact TEXT;
