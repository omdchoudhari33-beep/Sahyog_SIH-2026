# SAHYOG database and object storage

One Postgres database (PostGIS + pgvector), shared by services 3, 5, 6, 7,
8, 9 (each owns its own tables in it, applied via its own migration
file — see "Migration files and order" below), plus one S3-compatible
object storage instance (MinIO) shared by every service that handles a
citizen's raw audio or photo (1, 2, 5, 8).

This file is the single place that shows the *whole* schema and how the
object storage layer plugs into it. Each service's own README still owns
the operational detail (setup steps, env vars, endpoint contracts) — this
is the map, not a replacement for them.

## Why one database, not nine

Every table below lives in the same `dno_triage` Postgres database. That
was already the design before this document existed (see each
`schema*.sql` file's own header comment) — services 5-9 explicitly chose to
extend the Triage database rather than stand up their own, because most of
what they do is join against `active_tickets`. This document keeps that
decision and makes it legible in one place, and extends the same idiom to
media (one object storage instance, one registry table) instead of letting
every service invent its own local-disk convention, which is what had
actually happened (`local_audio/`, `temp_uploads/`, `closure_uploads/`,
`pilot_uploads/` — four different ad hoc folders, three of them deleting
their files after use).

## Extensions

```sql
CREATE EXTENSION IF NOT EXISTS postgis;   -- geometry(Point/Polygon, 4326), ST_DWithin, ST_Y/ST_X
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector: embedding columns + hnsw ANN index
```

Both are enabled once, in `3.Triage and route/schema.sql`. The Docker image
in `3.Triage and route/Dockerfile.postgres` builds `pgvector/pgvector:pg16`
with `postgresql-16-postgis-3` layered on top, since neither upstream image
ships both.

## Migration files and order

Each service's schema lives in its own `schema*.sql` file, applied manually
with `psql "$DATABASE_URL" -f <file>`. None are auto-run at service
startup. All are additive-only (`CREATE TABLE/INDEX IF NOT EXISTS`,
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) and safe to re-run. Apply in
this order (a later file may `ALTER` or `REFERENCES` an earlier one):

| # | File | Owning service | Creates |
|---|------|----------------|---------|
| 1 | `3.Triage and route/schema.sql` | 3. Triage and route | `active_tickets`, `cold_storage`, `validation_decisions` |
| 2 | `3.Triage and route/schema_002_dispatch_hook.sql` | 5. ULB Dispatch | `ulb_directory`, `ulb_contacts`, `escalation_matrix`, `dispatches`, `dispatch_events`, `closure_proofs`, `status_link_tokens` |
| 3 | `3.Triage and route/schema_003_media_objects.sql` | shared / object storage | `media_objects`; `active_tickets.report_photo_media_id`, `active_tickets.report_audio_media_id`, `closure_proofs.photo_media_id` |
| 4 | `6.Track B Innovation/schema.sql` | 6. Track B Innovation | `hei_registry`, `hei_capabilities`, `hei_matches`, `teams`, `proposals` |
| 5 | `6.Track B Innovation/schema_002_university_portal.sql` | 6. Track B Innovation | `hei_registry.password_hash`; `hei_sessions` |
| 6 | `7.Industry Partnership/schema.sql` | 7. Industry Partnership | `partners`, `partner_capabilities`, `partnership_matches`, `ip_agreements`, `milestone_fund_ledger`, `fund_releases`, `nep_credits` |
| 7 | `8.Lifecycle Outcome/schema.sql` | 8. Lifecycle Outcome | `milestones`, `milestone_evaluations`, `pilot_validations`, `handover_records`, `spinout_records`, `rd_outcome_feedback` |
| 8 | `8.Lifecycle Outcome/schema_002_pilot_media.sql` | shared / object storage | `pilot_validations.photo_media_id` |
| 9 | `9.Transparency Layer/schema.sql` | 9. Transparency Layer | `audit_log` |

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/dno_triage"
psql $env:DATABASE_URL -f "3.Triage and route/schema.sql"
psql $env:DATABASE_URL -f "3.Triage and route/schema_002_dispatch_hook.sql"
psql $env:DATABASE_URL -f "3.Triage and route/schema_003_media_objects.sql"
psql $env:DATABASE_URL -f "6.Track B Innovation/schema.sql"
psql $env:DATABASE_URL -f "6.Track B Innovation/schema_002_university_portal.sql"
psql $env:DATABASE_URL -f "7.Industry Partnership/schema.sql"
psql $env:DATABASE_URL -f "8.Lifecycle Outcome/schema.sql"
psql $env:DATABASE_URL -f "8.Lifecycle Outcome/schema_002_pilot_media.sql"
psql $env:DATABASE_URL -f "9.Transparency Layer/schema.sql"
```

## FK conventions used throughout

- **Hard FK to `active_tickets(id)` or `media_objects(id)`**: every
  service does this freely. Both are core infrastructure tables that exist
  before any feature-service migration runs, and everything downstream of
  a ticket needs to join against it anyway.
- **Hard FK within a service's own migration file**: e.g.
  `dispatches.contact_id -> ulb_contacts.id`, both created in
  `schema_002_dispatch_hook.sql`.
- **No FK ("loose reference"), documented in a comment**: an id that
  points at a table owned by a *different* service's migration file, e.g.
  `7.Industry Partnership`'s `partnership_matches.proposal_id` pointing at
  `6.Track B Innovation`'s `proposals.id`. This is deliberate, not an
  oversight — each service's schema file is applied independently and in
  build order, so a hard FK across that boundary would make one service's
  migration depend on another's having already run. If you are adding a
  new cross-service reference, follow this same rule: FK to
  `active_tickets`/`media_objects`, comment-only reference to anything else.

## Entity map

```
active_tickets (3. Triage and route)
 ├─ report_photo_media_id ──────┐
 ├─ report_audio_media_id ──────┤
 │                              ▼
 │                        media_objects (object storage registry)
 │                              ▲
 ├─ validation_decisions        │
 ├─ dispatches (5. ULB Dispatch)│
 │   ├─ dispatch_events         │
 │   └─ closure_proofs ─── photo_media_id
 ├─ hei_matches (6. Track B)
 │   └─ teams
 │       └─ proposals
 │           ├─ partnership_matches (7. Industry, loose ref)
 │           │   ├─ ip_agreements
 │           │   └─ milestone_fund_ledger ── fund_releases
 │           ├─ nep_credits (7. Industry, loose ref)
 │           └─ milestones (8. Lifecycle, loose ref)
 │               └─ milestone_evaluations
 ├─ pilot_validations (8. Lifecycle) ── photo_media_id
 ├─ handover_records (8. Lifecycle)
 ├─ spinout_records (8. Lifecycle, loose ref to proposals)
 ├─ rd_outcome_feedback (8. Lifecycle)
 └─ (referenced by entity_id from) audit_log (9. Transparency, untyped)
```

## Geospatial and vector design (already in place, kept as-is)

- `active_tickets.geom geometry(Point, 4326)` + `ulb_directory.boundary
  geometry(Polygon, 4326)`, both GIST-indexed. Dedup's geospatial pass uses
  `ST_DWithin(geom::geography, ..., radius_m)` for a real-meters radius
  query; ULB routing does the equivalent polygon-contains check.
- `active_tickets.embedding vector(384)` (all-MiniLM-L6-v2) and
  `hei_capabilities.embedding vector(384)`, both HNSW-indexed
  (`vector_cosine_ops`). Dedup's semantic pass and Track B's HEI matching
  both use `<=>` cosine distance the same way.

## Object storage architecture

**MinIO** (S3-compatible), one instance, two buckets: `sahyog-audio` and
`sahyog-images`. Brought up by `3.Triage and route/docker-compose.yml`
alongside Postgres. Buckets are created and set to public-read
automatically by each service's `object_storage.py` on first upload — not
by the compose file or a migration.

```
citizen audio/photo
       │
       ▼
 service-specific upload endpoint (1, 2, 5, or 8)
       │
       ├──► MinIO: PUT bucket/object_key ───────────► durable file, fetchable by URL
       │
       └──► Postgres: INSERT INTO media_objects ────► media_objects.id (best-effort)
                                                              │
                              active_tickets / closure_proofs / pilot_validations
                              reference it by *_media_id
```

### `media_objects` — the registry (in `3.Triage and route/schema_003_media_objects.sql`)

One row per uploaded file, keyed by `(bucket, object_key)`. Columns:
`media_type` (`audio`|`image`), `bucket`, `object_key`, `content_type`,
`size_bytes`, `checksum_sha256`, `original_filename`, `capture_lat`/
`capture_lon`/`exif_captured_at` (when known), `uploaded_by_service`,
`created_at`.

### Who uploads what

| Service | Upload point | Bucket | Registers in `media_objects`? |
|---|---|---|---|
| 1. Language normalizer | `POST /api/v1/audio/upload` | `sahyog-audio` | Optional (only if `DATABASE_URL` is set — this service has no other reason to talk to Postgres) |
| 2. Evidence Extractor | `POST /evidence/extract`, `POST /evidence/attach-photo` | `sahyog-images` | Optional (same reason) |
| 5. ULB Dispatch | `POST /status/{token}/update` (closure photo) | `sahyog-images` | Yes (already has `DATABASE_URL`) |
| 8. Lifecycle Outcome | `POST /admin/{ticket_id}/pilot-validate` | `sahyog-images` | Yes (already has `DATABASE_URL`) |

Registration is always **best-effort**: the object is uploaded to MinIO
first, and a `media_objects` insert failure (DB down, migration not yet
applied) is logged and swallowed rather than losing the upload or failing
the citizen-facing request. `media_id` is `None` in that case; the file is
still safely in object storage and still gets a usable URL, it just isn't
joinable from SQL until the row exists.

### How a citizen's original photo/audio reaches the ticket

Previously the citizen's photo bytes were held in memory / a temp file for
the duration of one request (S2 Evidence Extractor's `/evidence/extract`)
and then deleted — there was no durable copy anywhere, at any layer, once
a ticket existed. Same for audio: `1.Language normalizer`'s
`local_audio/` folder was the only copy, meant as an ASR working file, not
storage.

Now: S2 uploads the original (pre-resize) photo to `sahyog-images` and
returns `media.media_id` in its response; S1 uploads the recording to
`sahyog-audio` and returns `media_id` from `/audio/upload`.
`4.Orchestrator` threads both ids through
(`app/conversation.py`'s `report_photo_media_id`/`report_audio_media_id`
for the multi-turn flow, local variables for the one-shot `/submit` flow)
into `app/mapping.py:build_ticket_payload()`, which puts them on the
`IncomingTicket` sent to `POST /d2/ingest`. `3.Triage and route/app/
dedup.py` sets them on `active_tickets` when a *new* ticket is created (a
merge into an existing master keeps the master's media, on the reasoning
that cluster merges are about the same real-world issue, not about
replacing evidence).

`GET /dno/tickets` and `GET /dno/tickets/{id}` (both in `3.Triage and
route/app/validation.py`) `LEFT JOIN media_objects` and return
`report_photo_url`/`report_audio_url` as plain fetchable URLs, built from
`S3_PUBLIC_BASE_URL` + bucket + object key — no presigned-URL machinery,
since Triage never uploads anything itself and so never holds S3
credentials. The operator dashboard (`4.Orchestrator/static/dashboard.js`)
renders these directly.

### Closure/pilot-validation photos

`5.ULB Dispatch` and `8.Lifecycle Outcome` follow the same shape for
resolution evidence: upload to `sahyog-images`, get back `(media_id, url)`,
store both on `closure_proofs`/`pilot_validations` (`photo_media_id` is the
FK; `photo_url` is a denormalized convenience copy of the same object's
URL, kept because it was already a `NOT NULL` column other code reads
directly). The C3 vision-similarity check now posts the photo *bytes*
directly (`_get_vision_similarity`) instead of re-opening a local disk
path, since there may no longer be one.

### Honesty notes (same style as this repo's `audit_log` table)

- Buckets are public-read. There is no citizen-PII exposure beyond what's
  already visible in the photo/audio itself, and this is a hackathon-scope
  system — if that changes, switch to presigned URLs
  (`object_storage.py` would need a `presign()` method and every reader
  above would need to call it instead of building a URL by string
  concatenation; not implemented here).
- `media_objects` registration is best-effort, not transactional with the
  MinIO upload. A registration failure never rolls back or blocks the
  upload. This mirrors the existing "never let a vision-service/SMTP/
  Bhashini outage block the citizen-facing request" pattern already used
  throughout this repo.
- MinIO's default credentials (`sahyog` / `sahyog-dev-secret`) are
  hackathon/demo defaults, same posture as `ADMIN_FORM_PASSWORD` and the
  Postgres `postgres`/`postgres` credentials already in this repo. Rotate
  them (and switch `S3_USE_SSL=true`) before any real deployment.

## Config reference (`S3_*` env vars, same names in every service)

| Var | Default | Meaning |
|---|---|---|
| `S3_ENDPOINT_URL` | `http://localhost:9000` | MinIO S3 API endpoint |
| `S3_PUBLIC_BASE_URL` | `http://localhost:9000` | Base URL used to build fetchable links (may differ from the endpoint behind a reverse proxy) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `sahyog` / `sahyog-dev-secret` | Must match `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` in `3.Triage and route/docker-compose.yml` |
| `S3_REGION` | `us-east-1` | Required by the S3 API surface; meaningless for MinIO itself |
| `S3_USE_SSL` | `false` | Set `true` behind TLS |
| `S3_BUCKET_AUDIO` / `S3_BUCKET_IMAGES` | `sahyog-audio` / `sahyog-images` | |

## Where the code lives

- `app/object_storage.py` (or `object_storage.py` at the service root for
  "2. Evidence Extractor", which has no `app/` package): the `ObjectStorage`
  class. Copied, not imported, into each of the four services that upload
  media — same "each service stays independently deployable" idiom this
  repo already uses for e.g. the duplicated `haversine_meters` in
  `5.ULB Dispatch/app/closure.py` and `8.Lifecycle Outcome/app/closure.py`.
- `app/storage.py` (or `storage.py`): the module-level singleton built from
  that service's own settings, same pattern as `app/db.py`'s `engine`.
