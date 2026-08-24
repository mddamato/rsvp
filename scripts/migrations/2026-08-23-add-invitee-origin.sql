-- One-time migration for existing deployments (idempotent on the
-- ADD COLUMN; re-running after success will error on the constraint
-- already existing, which is fine to ignore on a manual re-run).
-- Fresh installs get this column from schema.sql directly and don't
-- need this file.
ALTER TABLE invitees
  ADD COLUMN IF NOT EXISTS origin VARCHAR NOT NULL DEFAULT 'admin';

ALTER TABLE invitees
  ADD CONSTRAINT invitees_origin_check CHECK (origin IN ('admin', 'self'));
