-- Multi-institution simultaneous collaboration (subgraph TB extension).
-- Sibling migration to schema.sql / schema_002/003, same convention:
--   psql "$DATABASE_URL" -f schema_004_multi_institution.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.
--
-- Does NOT touch uq_hei_matches_ticket_active (still one active 'proposed'
-- row per ticket - the primary-match cascade in matcher.py is unchanged).
-- This ADDS a second, independent guarantee: the SAME HEI can't hold two
-- rows for the SAME ticket (accidental double-registration), while
-- DIFFERENT HEIs can each hold their own row for the same ticket freely -
-- that's what makes app/matcher.py::register_interest()'s multi-
-- institution collaboration possible.

CREATE UNIQUE INDEX IF NOT EXISTS uq_hei_matches_ticket_hei
    ON hei_matches (ticket_id, hei_id);
