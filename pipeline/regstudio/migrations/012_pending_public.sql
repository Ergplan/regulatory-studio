-- An order may be shown on the public site before legal review, clearly marked "pending legal review".
-- It is a deliberate choice per order by a named person (regstudio publish-pending), never a default.
ALTER TABLE orders ADD COLUMN pending_public INTEGER NOT NULL DEFAULT 0;
