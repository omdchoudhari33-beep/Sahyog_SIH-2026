-- Track B Innovation schema (subgraph TB: R1, TB1-TB4)
-- Lives in the SAME Postgres instance/DB as "3.Triage and route" and
-- "5.ULB Dispatch" (pgvector + postgis already enabled there) - this
-- service owns its own tables, does not create a separate database.
--
-- Applied manually, same convention as the other services:
--   psql "$DATABASE_URL" -f schema.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.

CREATE TABLE IF NOT EXISTS hei_registry (
    id                      BIGSERIAL PRIMARY KEY,
    institution_name        TEXT NOT NULL,
    state                   TEXT NOT NULL,
    district                TEXT,
    contact_email           TEXT NOT NULL,
    contact_phone           TEXT,
    incubator_name          TEXT,
    capacity_active_projects INT NOT NULL DEFAULT 3,
    active                  BOOLEAN NOT NULL DEFAULT true,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Domain-tagged capability rows per HEI, embedded for semantic matching
-- against active_tickets.embedding (same all-MiniLM-L6-v2 / 384-dim model
-- Agent3 already uses - see app/embedding.py's reuse note).
CREATE TABLE IF NOT EXISTS hei_capabilities (
    id              BIGSERIAL PRIMARY KEY,
    hei_id          BIGINT NOT NULL REFERENCES hei_registry(id),
    domain          TEXT NOT NULL,
    department_name TEXT NOT NULL,
    description     TEXT NOT NULL,
    embedding       vector(384) NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hei_capabilities_embedding
    ON hei_capabilities USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS hei_matches (
    id                BIGSERIAL PRIMARY KEY,
    ticket_id         BIGINT NOT NULL REFERENCES active_tickets(id),
    hei_id            BIGINT NOT NULL REFERENCES hei_registry(id),
    capability_id     BIGINT REFERENCES hei_capabilities(id),
    similarity_score  REAL,
    status            TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','accepted','declined','expired')),
    decline_reason    TEXT,
    attempt_no        INT NOT NULL DEFAULT 1,
    match_token       TEXT NOT NULL UNIQUE,
    token_expires_at  TIMESTAMPTZ NOT NULL,
    decided_at        TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hei_matches_ticket ON hei_matches (ticket_id);
-- One active (non-terminal) match per ticket - mirrors
-- 5.ULB Dispatch's uq_dispatches_ticket_active exactly, same reasoning:
-- the DB constraint is the real guarantee under concurrency, not an
-- app-level check.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hei_matches_ticket_active
    ON hei_matches (ticket_id)
    WHERE status IN ('proposed');

CREATE TABLE IF NOT EXISTS teams (
    id                  BIGSERIAL PRIMARY KEY,
    match_id            BIGINT NOT NULL REFERENCES hei_matches(id),
    team_name           TEXT NOT NULL,
    faculty_mentor_name TEXT NOT NULL,
    faculty_mentor_email TEXT NOT NULL,
    student_names       JSONB NOT NULL DEFAULT '[]',
    formed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proposals (
    id                BIGSERIAL PRIMARY KEY,
    team_id           BIGINT NOT NULL REFERENCES teams(id),
    ticket_id         BIGINT NOT NULL REFERENCES active_tickets(id),
    title             TEXT NOT NULL,
    summary           TEXT NOT NULL,
    requested_budget  NUMERIC(12,2),
    timeline_weeks    INT,
    status            TEXT NOT NULL DEFAULT 'submitted'
                        CHECK (status IN ('submitted','nodal_review','approved','rejected','revision_requested')),
    nodal_officer_id  TEXT,
    nodal_notes       TEXT,
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_proposals_ticket ON proposals (ticket_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals (status);
