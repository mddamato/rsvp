-- One-time migration for existing deployments (idempotent). Adds the
-- reviewed column used to flag self-registered invitees the admin
-- hasn't confirmed yet. Default true means every existing row
-- (admin-created, from before this feature existed) counts as
-- already reviewed -- only new self-registrations start as false.
-- Fresh installs get this column from schema.sql directly and don't
-- need this file.
ALTER TABLE invitees
  ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT true;
