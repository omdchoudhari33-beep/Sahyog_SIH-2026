-- D2 Dedup Engine schema
-- Requires PostGIS and pgvector extensions

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- Active ticket DB (DB_Active in the diagram)
CREATE TABLE IF NOT EXISTS active_tickets (
    id                          BIGSERIAL PRIMARY KEY,
    master_ticket_id            BIGINT REFERENCES active_tickets(id),  -- NULL if this IS the master
    standardized_problem_statement TEXT NOT NULL,
    domain                      TEXT,
    urgency                     TEXT,
    severity                    REAL,
    population_impact           REAL,
    status                      TEXT NOT NULL DEFAULT 'active', -- active | resolved | merged
    cluster_count                INT NOT NULL DEFAULT 1,        -- N reports folded into this ticket
    priority_score               REAL,
    geom                        geometry(Point, 4326) NOT NULL,
    embedding                   vector(384) NOT NULL,           -- all-MiniLM-L6-v2 dim
    raw_evidence                 JSONB,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fast radius queries for the geospatial pass
CREATE INDEX IF NOT EXISTS idx_active_tickets_geom
    ON active_tickets USING GIST (geom);

-- Only index active (non-merged) tickets for the geospatial candidate scan
CREATE INDEX IF NOT EXISTS idx_active_tickets_geom_active
    ON active_tickets USING GIST (geom)
    WHERE status = 'active';

-- ANN index for the semantic pass (cosine distance)
-- ivfflat needs ANALYZE after enough rows exist; hnsw has no such requirement
CREATE INDEX IF NOT EXISTS idx_active_tickets_embedding
    ON active_tickets USING hnsw (embedding vector_cosine_ops);

-- Cold storage for spam/rejected tickets (D1 output)
CREATE TABLE IF NOT EXISTS cold_storage (
    id            BIGSERIAL PRIMARY KEY,
    reason        TEXT NOT NULL,   -- e.g. 'not_actionable', 'low_confidence_nonsensical'
    raw_payload   JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- DNO human validation audit trail. Run this migration after the base schema.
CREATE TABLE IF NOT EXISTS validation_decisions (
    id            BIGSERIAL PRIMARY KEY,
    ticket_id     BIGINT NOT NULL REFERENCES active_tickets(id),
    decision      TEXT NOT NULL CHECK (decision IN ('track_a', 'track_b', 'reject_merge')),
    operator_id   TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_validation_decisions_ticket_id
    ON validation_decisions(ticket_id);

-- S2 Evidence Extractor already reasons about Track A vs Track B per report
-- (LLM-based, considers complexity, not just domain). Carry that suggestion
-- through so D4 doesn't have to re-derive it from domain alone. Run this
-- migration after the base schema.
ALTER TABLE active_tickets ADD COLUMN IF NOT EXISTS ai_suggested_track TEXT;
