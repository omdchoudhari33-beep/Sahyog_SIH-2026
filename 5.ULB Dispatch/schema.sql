-- 5. ULB Dispatch (Track A) schema.
-- Lives in the SAME Postgres instance/DB as "3.Triage and route" (PostGIS
-- already enabled there) - this service owns its own tables, does not
-- create a separate database. dispatches/closure_proofs FK into
-- active_tickets (3.Triage/schema.sql) and media_objects
-- (3.Triage/schema_003_media_objects.sql) - apply those first.
--
-- Applied manually, same convention as every other migration in this repo:
--   psql "$DATABASE_URL" -f schema.sql
-- NOT auto-run by any service at startup. Additive only (CREATE TABLE/INDEX
-- IF NOT EXISTS), safe to re-run.

CREATE TABLE IF NOT EXISTS ulb_directory (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    state       TEXT NOT NULL,
    district    TEXT,
    boundary    geometry(Polygon, 4326) NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Point-in-polygon ULB resolution (app/router.py::_resolve_ulb_id) - every
-- ticket's geom is tested against every active boundary.
CREATE INDEX IF NOT EXISTS idx_ulb_directory_boundary ON ulb_directory USING GIST (boundary);

CREATE TABLE IF NOT EXISTS ulb_contacts (
    id             BIGSERIAL PRIMARY KEY,
    ulb_id         BIGINT NOT NULL REFERENCES ulb_directory(id),
    domain         TEXT,  -- NULL = catch-all for this ULB/level (the common case, not an edge case)
    dept_name      TEXT NOT NULL,
    level          INT NOT NULL DEFAULT 1,
    channel        TEXT NOT NULL CHECK (channel IN ('api', 'email')),
    email          TEXT,
    api_endpoint   TEXT,
    api_key_ref    TEXT,
    officer_name   TEXT,
    officer_phone  TEXT,
    verified_at    TIMESTAMPTZ,
    active         BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ulb_contacts_ulb_domain ON ulb_contacts (ulb_id, domain, level) WHERE active;
-- At most one active contact per (ulb, level, domain) - COALESCE so the
-- catch-all (domain IS NULL) row is also covered by the uniqueness check,
-- not exempted by NULL's usual not-distinct-from-itself behaviour.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ulb_contacts_ulb_domain_level
    ON ulb_contacts (ulb_id, level, COALESCE(domain, ''))
    WHERE active;

CREATE TABLE IF NOT EXISTS dispatches (
    id                BIGSERIAL PRIMARY KEY,
    ticket_id         BIGINT NOT NULL REFERENCES active_tickets(id),
    ulb_id            BIGINT NOT NULL REFERENCES ulb_directory(id),
    contact_id        BIGINT NOT NULL REFERENCES ulb_contacts(id),
    channel           TEXT NOT NULL CHECK (channel IN ('api', 'email')),
    correlation_code  TEXT NOT NULL UNIQUE,
    status            TEXT NOT NULL DEFAULT 'sent'
                        CHECK (status IN ('sent', 'acked', 'in_progress', 'overdue', 'escalated', 'resolved', 'disputed')),
    level             INT NOT NULL DEFAULT 1,
    attempt_no        INT NOT NULL DEFAULT 1,
    sent_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dispatches_ticket ON dispatches (ticket_id);
-- SLA/escalation sweep only scans dispatches still in flight.
CREATE INDEX IF NOT EXISTS idx_dispatches_status_sent_at ON dispatches (status, sent_at)
    WHERE status NOT IN ('resolved', 'disputed');
-- One active (non-terminal) dispatch per ticket - the real concurrency
-- guarantee app-level checks in dispatch.py are only a courtesy fast path
-- for (mirrored by 6.Track B Innovation's uq_hei_matches_ticket_active).
CREATE UNIQUE INDEX IF NOT EXISTS uq_dispatches_ticket_active
    ON dispatches (ticket_id)
    WHERE status NOT IN ('resolved', 'disputed');

CREATE TABLE IF NOT EXISTS dispatch_events (
    id            BIGSERIAL PRIMARY KEY,
    dispatch_id   BIGINT NOT NULL REFERENCES dispatches(id),
    event_type    TEXT NOT NULL
                    CHECK (event_type IN ('sent', 'bounced', 'acked', 'replied', 'escalated', 'resolved', 'disputed', 'api_error')),
    payload       JSONB,
    source        TEXT NOT NULL CHECK (source IN ('email', 'api', 'status_link', 'citizen', 'system')),
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dispatch_events_dispatch ON dispatch_events (dispatch_id);

CREATE TABLE IF NOT EXISTS closure_proofs (
    id                 BIGSERIAL PRIMARY KEY,
    ticket_id          BIGINT NOT NULL REFERENCES active_tickets(id),
    dispatch_id        BIGINT NOT NULL REFERENCES dispatches(id),
    photo_url          TEXT NOT NULL,
    photo_media_id     BIGINT REFERENCES media_objects(id),
    photo_lat          DOUBLE PRECISION,
    photo_lon          DOUBLE PRECISION,
    exif_captured_at   TIMESTAMPTZ,
    similarity_score   REAL,
    geo_check_passed   BOOLEAN,
    citizen_confirmed  BOOLEAN,
    submitted_by       TEXT NOT NULL CHECK (submitted_by IN ('officer', 'citizen')),
    verified_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_closure_proofs_ticket ON closure_proofs (ticket_id);

CREATE TABLE IF NOT EXISTS status_link_tokens (
    id            BIGSERIAL PRIMARY KEY,
    dispatch_id   BIGINT NOT NULL REFERENCES dispatches(id),
    token         TEXT NOT NULL UNIQUE,
    used_at       TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escalation_matrix (
    id          BIGSERIAL PRIMARY KEY,
    domain      TEXT NOT NULL,
    level       INT NOT NULL,
    sla_hours   INT NOT NULL,
    UNIQUE (domain, level)
);
