-- Solution document upload for proposals (University Portal). Sibling
-- migration to schema.sql / schema_002-004, same convention:
--   psql "$DATABASE_URL" -f schema_005_proposal_documents.sql
-- NOT auto-run by any service at startup.
--
-- Widens "3.Triage and route/schema_003_media_objects.sql"'s media_type
-- CHECK constraint (previously only 'audio'/'image') to add 'document' -
-- this is the first service to upload a PDF rather than a photo/recording.
-- DROP+ADD is required (Postgres has no ALTER CHECK), but is safe to
-- re-run: DROP...IF EXISTS, then ADD only re-executes if the constraint
-- doesn't already have 'document' in it (guarded by a DO block so a
-- second run doesn't error on a duplicate constraint name).

DO $$
BEGIN
    ALTER TABLE media_objects DROP CONSTRAINT IF EXISTS media_objects_media_type_check;
    ALTER TABLE media_objects ADD CONSTRAINT media_objects_media_type_check
        CHECK (media_type IN ('audio', 'image', 'document'));
END $$;

ALTER TABLE proposals ADD COLUMN IF NOT EXISTS solution_document_media_id BIGINT REFERENCES media_objects(id);
