-- Draft regulations and weekly editions may also be shown before legal review, marked "awaiting legal review".
ALTER TABLE consultations ADD COLUMN pending_public INTEGER NOT NULL DEFAULT 0;
ALTER TABLE digests ADD COLUMN pending_public INTEGER NOT NULL DEFAULT 0;
