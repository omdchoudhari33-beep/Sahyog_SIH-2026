-- Transparency Layer schema (subgraph X: X1-X3)
-- Lives in the SAME Postgres instance/DB as the other services - owns its
-- own tables, does not create a separate database.
--
-- Applied manually: psql "$DATABASE_URL" -f schema.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.

-- Append-only audit log (X3). True immutability (DB-role REVOKE UPDATE/
-- DELETE, hash-chaining) is TODO(human) - this MVP is an honesty
-- guarantee (the app never issues UPDATE/DELETE against this table), not a
-- cryptographic one. Documented plainly here and in README, not glossed over.
CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    service_name  TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_id     BIGINT NOT NULL,
    event         TEXT NOT NULL,
    actor         TEXT,
    payload       JSONB,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_occurred_at ON audit_log (occurred_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_service ON audit_log (service_name);
