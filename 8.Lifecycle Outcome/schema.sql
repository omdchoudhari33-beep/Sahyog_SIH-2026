-- Lifecycle Outcome schema (subgraph F: F1-F4)
-- Lives in the SAME Postgres instance/DB as the other services - owns its
-- own tables, does not create a separate database.
--
-- Applied manually: psql "$DATABASE_URL" -f schema.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.

-- proposal_id is a loose reference to "6.Track B Innovation"'s proposals(id)
-- - same reasoning as "7.Industry Partnership"'s schema.sql: no cross-service
-- FK, each service's migration is applied independently.
CREATE TABLE IF NOT EXISTS milestones (
    id            BIGSERIAL PRIMARY KEY,
    proposal_id   BIGINT NOT NULL,
    sequence_no   INT NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    target_date   DATE,
    status        TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','submitted','evaluated_pass','evaluated_fail')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_milestones_proposal ON milestones (proposal_id);

CREATE TABLE IF NOT EXISTS milestone_evaluations (
    id              BIGSERIAL PRIMARY KEY,
    milestone_id    BIGINT NOT NULL REFERENCES milestones(id),
    evaluator_name  TEXT NOT NULL,
    score           REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    notes           TEXT,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_milestone_evaluations_milestone ON milestone_evaluations (milestone_id);

CREATE TABLE IF NOT EXISTS pilot_validations (
    id                  BIGSERIAL PRIMARY KEY,
    ticket_id           BIGINT NOT NULL REFERENCES active_tickets(id),
    proposal_id         BIGINT NOT NULL,
    photo_url           TEXT NOT NULL,
    photo_lat           DOUBLE PRECISION,
    photo_lon           DOUBLE PRECISION,
    geo_check_passed    BOOLEAN,
    similarity_score    REAL,
    verdict             TEXT NOT NULL DEFAULT 'pending_review'
                          CHECK (verdict IN ('pass','fail','pending_review')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pilot_validations_ticket ON pilot_validations (ticket_id);

-- ulb_dispatch_id is a loose reference to "5.ULB Dispatch"'s dispatches(id) -
-- same no-cross-service-FK reasoning as above.
CREATE TABLE IF NOT EXISTS handover_records (
    id                  BIGSERIAL PRIMARY KEY,
    ticket_id           BIGINT NOT NULL REFERENCES active_tickets(id),
    ulb_dispatch_id     BIGINT,
    handover_notes      TEXT,
    handed_over_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_handover_records_ticket ON handover_records (ticket_id);

CREATE TABLE IF NOT EXISTS spinout_records (
    id              BIGSERIAL PRIMARY KEY,
    proposal_id     BIGINT NOT NULL,
    startup_name    TEXT NOT NULL,
    incubator_name  TEXT,
    notes           TEXT,
    spun_out_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_spinout_records_proposal ON spinout_records (proposal_id);

-- Captures the "resolution outcome retrains classifier" signal from the
-- architecture diagram. Recording the signal is real; the actual
-- retraining job that reads this table is TODO(human) / future work.
CREATE TABLE IF NOT EXISTS rd_outcome_feedback (
    id            BIGSERIAL PRIMARY KEY,
    ticket_id     BIGINT NOT NULL REFERENCES active_tickets(id),
    outcome       TEXT NOT NULL CHECK (outcome IN ('pilot_pass','pilot_fail','spinout')),
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rd_outcome_feedback_ticket ON rd_outcome_feedback (ticket_id);
