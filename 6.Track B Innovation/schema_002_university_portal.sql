-- University Portal: real per-HEI login (subgraph TB extension).
-- Sibling migration to schema.sql, same convention: applied manually via
--   psql "$DATABASE_URL" -f schema_002_university_portal.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.

ALTER TABLE hei_registry ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Server-side session store (not a signed cookie/JWT) - same auditable,
-- revocable-by-deleting-the-row idiom as every token table elsewhere in
-- this repo (hei_matches.match_token, 5.ULB Dispatch's status_link_tokens).
CREATE TABLE IF NOT EXISTS hei_sessions (
    id            BIGSERIAL PRIMARY KEY,
    hei_id        BIGINT NOT NULL REFERENCES hei_registry(id),
    session_token TEXT NOT NULL UNIQUE,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hei_sessions_hei ON hei_sessions (hei_id);
