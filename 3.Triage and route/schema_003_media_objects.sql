-- 003_media_objects.sql
-- Object storage registry (MinIO / any S3-compatible endpoint). Every audio
-- or image file the pipeline persists gets exactly one row here, keyed by
-- (bucket, object_key) - this table is the single source of truth for
-- "what media exists and where", replacing the old pattern of writing a raw
-- local-disk path (e.g. "closure_uploads/<uuid>.jpg") straight into a TEXT
-- column. Feature tables reference it by id instead of embedding storage
-- details themselves.
--
-- Lives in the SAME Postgres instance/DB as the other services, same as
-- schema_002_dispatch_hook.sql. Applied manually, same convention:
--   psql "$DATABASE_URL" -f schema_003_media_objects.sql
-- NOT auto-run by any service at startup. Additive only, safe to re-run.
-- Requires schema.sql and schema_002_dispatch_hook.sql to have been applied
-- first (this migration alters active_tickets and closure_proofs).

CREATE TABLE IF NOT EXISTS media_objects (
    id                    BIGSERIAL PRIMARY KEY,
    media_type            TEXT NOT NULL CHECK (media_type IN ('audio', 'image')),
    bucket                TEXT NOT NULL,
    object_key            TEXT NOT NULL,
    content_type          TEXT NOT NULL,
    size_bytes            BIGINT NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256       TEXT,
    original_filename     TEXT,
    -- EXIF/device capture metadata, when known at upload time (mirrors
    -- 2.Evidence Extractor's Geolocation shape) - lets a media row answer
    -- "where/when was this actually captured" without re-opening the file.
    capture_lat           DOUBLE PRECISION,
    capture_lon           DOUBLE PRECISION,
    exif_captured_at      TIMESTAMPTZ,
    -- Which service's upload path created this row (e.g. "1.language_normalizer",
    -- "2.evidence_extractor", "5.ulb_dispatch", "8.lifecycle_outcome") - purely
    -- informational, not a FK to anything.
    uploaded_by_service   TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_media_objects_bucket_key ON media_objects (bucket, object_key);
CREATE INDEX IF NOT EXISTS idx_media_objects_type ON media_objects (media_type);
CREATE INDEX IF NOT EXISTS idx_media_objects_service ON media_objects (uploaded_by_service);

-- Original citizen-submitted evidence (S2 Evidence Extractor's inputs and
-- S1 Language Normalizer's ASR audio), persisted durably for the first time.
-- Previously these bytes were processed in memory / a temp file and thrown
-- away once a ticket existed - a citizen's or officer's only record of what
-- was actually submitted was whatever ended up in raw_evidence JSONB (text
-- only). Both columns are nullable: not every report has a photo, and
-- text-only reports have no audio.
ALTER TABLE active_tickets ADD COLUMN IF NOT EXISTS report_photo_media_id BIGINT REFERENCES media_objects(id);
ALTER TABLE active_tickets ADD COLUMN IF NOT EXISTS report_audio_media_id BIGINT REFERENCES media_objects(id);

-- Closure proof photo. photo_url stays NOT NULL (existing contract, existing
-- readers) but from this migration on it is populated with the durable
-- object storage URL instead of a local "closure_uploads/<uuid>.jpg" disk
-- path. photo_media_id is the authoritative FK; photo_url is a denormalized
-- convenience copy for callers that just want a link.
ALTER TABLE closure_proofs ADD COLUMN IF NOT EXISTS photo_media_id BIGINT REFERENCES media_objects(id);
