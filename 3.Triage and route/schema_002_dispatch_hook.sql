-- 002_dispatch_hook.sql
-- Additive only. Safe to run multiple times. Never drops or alters existing columns.
-- Applied manually, same convention as schema.sql:
--   psql "$DATABASE_URL" -f schema.sql
--   psql "$DATABASE_URL" -f schema_002_dispatch_hook.sql
-- NOT applied automatically by any service at startup (Triage or Dispatch).
--
-- Owned by the "5.ULB Dispatch" service (port 8004), but lives in this same
-- database (PostGIS already enabled here) rather than a separate DB, per
-- that service's design. See 5.ULB Dispatch/README.md for the full picture.

CREATE TABLE IF NOT EXISTS ulb_directory (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    state         TEXT NOT NULL,
    district      TEXT,
    boundary      geometry(Polygon, 4326) NOT NULL,
    active        BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ulb_directory_boundary
    ON ulb_directory USING GIST (boundary);

CREATE TABLE IF NOT EXISTS ulb_contacts (
    id              BIGSERIAL PRIMARY KEY,
    ulb_id          BIGINT NOT NULL REFERENCES ulb_directory(id),
    domain          TEXT,                    -- NULL = catch-all contact for this ULB (see note below); non-NULL = a real domain-specific contact where one exists
    dept_name       TEXT NOT NULL,
    level           INT NOT NULL DEFAULT 1,  -- 1 = first contact, 2 = escalation, 3 = ...
    channel         TEXT NOT NULL CHECK (channel IN ('api', 'email')),
    email           TEXT,
    api_endpoint    TEXT,
    api_key_ref     TEXT,                    -- name of the env var holding the secret, never the secret itself
    officer_name    TEXT,
    officer_phone   TEXT,
    verified_at     TIMESTAMPTZ,             -- set once OTP/manual verification is done; NULL = unverified, do not trust closure claims from this contact
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- NOTE on domain being nullable: real-world ULB contact data (confirmed against
-- Jharkhand's Urban Development & Housing Department listings) is almost always
-- a single generic office email per ULB, not a department-specific one. A NULL
-- domain row is that catch-all contact. Do NOT treat NULL as an error case or
-- assume every ULB will eventually get domain-specific rows filled in — for
-- most ULBs, the catch-all IS the permanent, correct contact.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ulb_contacts_ulb_domain_level
    ON ulb_contacts (ulb_id, level, COALESCE(domain, ''))
    WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_ulb_contacts_ulb_domain
    ON ulb_contacts (ulb_id, domain, level) WHERE active = true;

CREATE TABLE IF NOT EXISTS escalation_matrix (
    id                BIGSERIAL PRIMARY KEY,
    domain            TEXT NOT NULL,
    level             INT NOT NULL,
    sla_hours         INT NOT NULL,          -- business hours before escalating to next level
    UNIQUE (domain, level)
);

CREATE TABLE IF NOT EXISTS dispatches (
    id                BIGSERIAL PRIMARY KEY,
    ticket_id         BIGINT NOT NULL REFERENCES active_tickets(id),
    ulb_id            BIGINT NOT NULL REFERENCES ulb_directory(id),
    contact_id        BIGINT NOT NULL REFERENCES ulb_contacts(id),
    channel           TEXT NOT NULL CHECK (channel IN ('api', 'email')),
    correlation_code  TEXT NOT NULL UNIQUE,
    status            TEXT NOT NULL DEFAULT 'sent'
                        CHECK (status IN ('sent','acked','in_progress','overdue','escalated','resolved','disputed')),
    level             INT NOT NULL DEFAULT 1,
    attempt_no        INT NOT NULL DEFAULT 1,
    sent_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dispatches_ticket ON dispatches (ticket_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_status_sent_at ON dispatches (status, sent_at) WHERE status NOT IN ('resolved','disputed');

-- Prevents the fire-and-forget webhook (Step 6) and the reconcile sweep
-- (Step 7) from ever racing each other into creating two active dispatches
-- for the same ticket. This is a DB-level guarantee; the app-level
-- idempotency check in dispatch.py is NOT sufficient on its own under
-- concurrent calls, and must not be treated as a substitute for this index.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dispatches_ticket_active
    ON dispatches (ticket_id)
    WHERE status NOT IN ('resolved', 'disputed');

CREATE TABLE IF NOT EXISTS dispatch_events (
    id            BIGSERIAL PRIMARY KEY,
    dispatch_id   BIGINT NOT NULL REFERENCES dispatches(id),
    event_type    TEXT NOT NULL CHECK (event_type IN
                    ('sent','bounced','acked','replied','escalated','resolved','disputed','api_error')),
    payload       JSONB,
    source        TEXT NOT NULL CHECK (source IN ('email','api','status_link','citizen','system')),
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dispatch_events_dispatch ON dispatch_events (dispatch_id);

CREATE TABLE IF NOT EXISTS closure_proofs (
    id                  BIGSERIAL PRIMARY KEY,
    ticket_id           BIGINT NOT NULL REFERENCES active_tickets(id),
    dispatch_id         BIGINT NOT NULL REFERENCES dispatches(id),
    photo_url           TEXT NOT NULL,
    photo_lat           DOUBLE PRECISION,
    photo_lon           DOUBLE PRECISION,
    exif_captured_at    TIMESTAMPTZ,
    similarity_score    REAL,                -- from C3 vision classifier comparison, 0-1
    geo_check_passed    BOOLEAN,
    citizen_confirmed   BOOLEAN,
    submitted_by        TEXT NOT NULL CHECK (submitted_by IN ('officer','citizen')),
    verified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_closure_proofs_ticket ON closure_proofs (ticket_id);

-- One-time status-link tokens for officers (no login system needed)
CREATE TABLE IF NOT EXISTS status_link_tokens (
    id            BIGSERIAL PRIMARY KEY,
    dispatch_id   BIGINT NOT NULL REFERENCES dispatches(id),
    token         TEXT NOT NULL UNIQUE,
    used_at       TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Escalation SLA defaults, one level 1->2 row per Track A domain (matches
-- 3.Triage and route/app/validation.py's TRACK_A_DOMAINS set).
-- TODO(human): confirm against actual Right-to-Service Act timelines for
-- this state before relying on these numbers in production - they are
-- placeholder defaults (shorter for emergencies, longer for routine
-- maintenance-type domains), not sourced from any real policy document.
INSERT INTO escalation_matrix (domain, level, sla_hours) VALUES
    ('CIVIC_DISASTER_EMERGENCY', 1, 4),
    ('DRAINAGE_WATERLOGGING', 1, 12),
    ('WATER_SUPPLY', 1, 12),
    ('ENERGY_POWER', 1, 12),
    ('SANITATION_SEWAGE', 1, 24),
    ('STRAY_ANIMAL_MANAGEMENT', 1, 24),
    ('ROADS_BRIDGES', 1, 48),
    ('TRAFFIC_SIGNAGE', 1, 48),
    ('HEALTHCARE_FACILITY_MAINTENANCE', 1, 48),
    ('STREETLIGHTING', 1, 72),
    ('WASTE_GARBAGE_COLLECTION', 1, 72),
    ('PARKS_PUBLIC_SPACES', 1, 72),
    ('EDUCATION_FACILITY_MAINTENANCE', 1, 72)
ON CONFLICT (domain, level) DO NOTHING;
