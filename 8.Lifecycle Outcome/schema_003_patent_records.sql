-- Patent/IP filing registry (F4 extension). Sibling migration to schema.sql
-- / schema_002_pilot_media.sql, same convention:
--   psql "$DATABASE_URL" -f schema_003_patent_records.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.
--
-- Independent of spinout_records/handover_records: a patent can be filed
-- regardless of whether the ticket also went to handover or spin-out, so
-- it's tracked as its own action, not a third "disposition" value.

CREATE TABLE IF NOT EXISTS patent_records (
    id                  BIGSERIAL PRIMARY KEY,
    ticket_id           BIGINT NOT NULL REFERENCES active_tickets(id),
    proposal_id         BIGINT NOT NULL,
    title               TEXT NOT NULL,
    applicant_names     JSONB NOT NULL DEFAULT '[]',
    filing_status       TEXT NOT NULL DEFAULT 'filed'
                          CHECK (filing_status IN ('filed', 'published', 'granted', 'abandoned')),
    application_number  TEXT,
    filed_at            TIMESTAMPTZ,
    granted_at          TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_patent_records_ticket ON patent_records (ticket_id);
