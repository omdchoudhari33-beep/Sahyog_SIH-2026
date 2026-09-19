-- Broadcast problem briefs to the top-N matching HEIs (subgraph TB extension).
-- Sibling migration to schema.sql / schema_002_university_portal.sql, same
-- convention: applied manually via
--   psql "$DATABASE_URL" -f schema_003_hei_broadcast.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.
--
-- This does NOT replace hei_matches / the accept-decline state machine -
-- it is a purely informational fan-out: every one of the top-N HEIs (by
-- cosine similarity) gets the problem brief, so more than one institution
-- can see and act on an opportunity even though only one hei_matches row is
-- ever "proposed" at a time (see matcher.py's uq_hei_matches_ticket_active).

CREATE TABLE IF NOT EXISTS hei_broadcast_notices (
    id                BIGSERIAL PRIMARY KEY,
    ticket_id         BIGINT NOT NULL REFERENCES active_tickets(id),
    hei_id            BIGINT NOT NULL REFERENCES hei_registry(id),
    capability_id     BIGINT NOT NULL REFERENCES hei_capabilities(id),
    rank              INT NOT NULL,
    similarity_score  REAL NOT NULL,
    brief_html        TEXT NOT NULL,
    sent_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticket_id, hei_id)
);
CREATE INDEX IF NOT EXISTS idx_hei_broadcast_notices_ticket ON hei_broadcast_notices (ticket_id);
CREATE INDEX IF NOT EXISTS idx_hei_broadcast_notices_hei ON hei_broadcast_notices (hei_id);
