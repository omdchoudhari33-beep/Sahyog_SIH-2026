-- Industry Partnership schema (subgraph I: I1-I5)
-- Lives in the SAME Postgres instance/DB as the other services - owns its
-- own tables, does not create a separate database.
--
-- Applied manually: psql "$DATABASE_URL" -f schema.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.

CREATE TABLE IF NOT EXISTS partners (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('industry','msme','startup','csr','lab')),
    sector          TEXT,
    contact_name    TEXT,
    contact_email   TEXT NOT NULL,
    contact_phone   TEXT,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS partner_capabilities (
    id              BIGSERIAL PRIMARY KEY,
    partner_id      BIGINT NOT NULL REFERENCES partners(id),
    domain          TEXT NOT NULL,
    offering_type   TEXT NOT NULL CHECK (offering_type IN ('mentorship','sponsorship','both')),
    notes           TEXT,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_partner_capabilities_domain ON partner_capabilities (domain) WHERE active;

-- proposal_id is a loose reference to "6.Track B Innovation"'s proposals(id)
-- (same DB instance, but intentionally no cross-service FK constraint here -
-- each service's schema.sql is applied independently and in build order,
-- so a hard FK would make Industry's migration depend on Track B's having
-- run first; documented here rather than silently assumed).
CREATE TABLE IF NOT EXISTS partnership_matches (
    id                BIGSERIAL PRIMARY KEY,
    proposal_id       BIGINT NOT NULL,
    partner_id        BIGINT NOT NULL REFERENCES partners(id),
    match_type        TEXT NOT NULL CHECK (match_type IN ('mentorship','sponsorship','both')),
    status            TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','accepted','declined')),
    match_token       TEXT NOT NULL UNIQUE,
    token_expires_at  TIMESTAMPTZ NOT NULL,
    decided_at        TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_partnership_matches_proposal ON partnership_matches (proposal_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_partnership_matches_proposal_active
    ON partnership_matches (proposal_id)
    WHERE status = 'proposed';

-- Tiered IP Ownership Template (I3). Real legal template content and any
-- e-signature integration are TODO(human) - this records which tier was
-- agreed, not the legal document itself.
CREATE TABLE IF NOT EXISTS ip_agreements (
    id                BIGSERIAL PRIMARY KEY,
    proposal_id       BIGINT NOT NULL,
    partner_id        BIGINT REFERENCES partners(id),
    tier              TEXT NOT NULL CHECK (tier IN ('hei_owned','shared','partner_owned','open_source')),
    template_version  TEXT NOT NULL DEFAULT 'v1-placeholder',
    document_url      TEXT,
    agreed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ip_agreements_proposal ON ip_agreements (proposal_id);

-- Milestone Fund Ledger (I4). Tracks committed/released AMOUNTS only - does
-- NOT move real money. escrow_provider is a label for a future real
-- integration (diagram: "oscrow via partner bank / PFMS - future").
CREATE TABLE IF NOT EXISTS milestone_fund_ledger (
    id                      BIGSERIAL PRIMARY KEY,
    proposal_id             BIGINT NOT NULL,
    partner_id              BIGINT REFERENCES partners(id),
    total_committed_amount  NUMERIC(12,2) NOT NULL,
    currency                TEXT NOT NULL DEFAULT 'INR',
    status                  TEXT NOT NULL DEFAULT 'committed'
                              CHECK (status IN ('committed','partially_released','fully_released','cancelled')),
    escrow_provider         TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_milestone_fund_ledger_proposal ON milestone_fund_ledger (proposal_id);

-- milestone_id is a loose reference to "8.Lifecycle Outcome"'s milestones(id)
-- - same reasoning as proposal_id above: no cross-service FK, documented.
CREATE TABLE IF NOT EXISTS fund_releases (
    id                BIGSERIAL PRIMARY KEY,
    ledger_id         BIGINT NOT NULL REFERENCES milestone_fund_ledger(id),
    milestone_id      BIGINT,
    amount_released   NUMERIC(12,2) NOT NULL,
    released_by       TEXT NOT NULL,
    released_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fund_releases_ledger ON fund_releases (ledger_id);

-- NEP Academic Credit & CSR Certificate (I5). Records that credits/
-- certificates were issued and by whom - real NEP academic-system
-- integration and real certificate generation/signing are TODO(human).
CREATE TABLE IF NOT EXISTS nep_credits (
    id                BIGSERIAL PRIMARY KEY,
    proposal_id       BIGINT NOT NULL,
    team_member_name  TEXT NOT NULL,
    credit_type       TEXT NOT NULL CHECK (credit_type IN ('nep_academic_credit','csr_certificate')),
    credits_awarded   NUMERIC(5,2),
    certificate_url   TEXT,
    issued_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_nep_credits_proposal ON nep_credits (proposal_id);
