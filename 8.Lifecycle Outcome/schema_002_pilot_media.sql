-- 002_pilot_media.sql
-- Sibling migration to schema.sql, same convention: applied manually via
--   psql "$DATABASE_URL" -f schema_002_pilot_media.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.
-- Requires "3.Triage and route/schema_003_media_objects.sql" to have been
-- applied first (media_objects table, same DB instance).

-- Pilot validation photo, same treatment as 5.ULB Dispatch's closure_proofs:
-- photo_url stays NOT NULL and now holds the durable object storage URL
-- instead of a local "pilot_uploads/<uuid>.jpg" disk path; photo_media_id
-- is the authoritative FK to the object storage registry. media_objects is
-- core infra (same tier as active_tickets), so this is a real FK, not the
-- loose "no cross-service FK" pattern used for proposals/milestones ids.
ALTER TABLE pilot_validations ADD COLUMN IF NOT EXISTS photo_media_id BIGINT REFERENCES media_objects(id);
