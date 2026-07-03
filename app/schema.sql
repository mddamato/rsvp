-- Applied automatically on first container start via
-- /docker-entrypoint-initdb.d in the postgres image.

CREATE TABLE IF NOT EXISTS invitees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lookup_phrase VARCHAR NOT NULL UNIQUE,
    primary_name VARCHAR NOT NULL,
    email VARCHAR,
    max_guests INT NOT NULL DEFAULT 0,
    rsvp_status VARCHAR NOT NULL DEFAULT 'Pending',
    plus_one_details TEXT,
    comments TEXT
);

CREATE INDEX IF NOT EXISTS idx_invitees_email ON invitees (lower(email));

CREATE TABLE IF NOT EXISTS rsvp_history (
    id SERIAL PRIMARY KEY,
    invitee_id UUID NOT NULL REFERENCES invitees(id) ON DELETE CASCADE,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    old_status VARCHAR NOT NULL,
    new_status VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_invitee ON rsvp_history (invitee_id);
