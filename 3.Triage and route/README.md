# D2 Dedup Cluster Engine

Implements Step 2 from Agent_D: geospatial + semantic deduplication of
incoming civic tickets against the active ticket DB, using a free,
self-hosted embedding model (no per-call API cost).

## Stack
- **FastAPI** — service layer
- **PostgreSQL + PostGIS + pgvector** — single DB for geometry and embeddings
- **sentence-transformers (`all-MiniLM-L6-v2`)** — free, self-hosted 384-dim embeddings

## Setup

1. Postgres with PostGIS and pgvector extensions available. The included
   `docker-compose.yml` builds the required image.
2. Start the database and run the schema:
   ```bash
   docker compose up -d --build
   psql "$DATABASE_URL" -f schema.sql
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and adjust `DATABASE_URL` if needed. The
   embedding model downloads automatically on first run (cached locally
   after that — no cost, no API key).
5. Run the service:
   ```bash
   uvicorn app.main:app --reload
   ```

## Endpoint

`POST /d2/ingest` — body matches `IncomingTicket` (the post-D1 ticket
shape: `standardized_problem_statement`, `domain`, `urgency`, `severity`,
`population_impact`, `latitude`, `longitude`, `raw_evidence`).

Returns whether the ticket was merged into an existing cluster or created
as a new active ticket, plus the cosine similarity score that drove the
decision.

## Tuning

All thresholds live in `app/config.py` / `.env`:
- `GEO_RADIUS_METERS` (default 100m) — geospatial candidate radius
- `SIMILARITY_MERGE_THRESHOLD` (default 0.85) — cosine similarity cutoff for merging
- `GEO_CANDIDATE_LIMIT` (default 25) — max nearby tickets considered per new report

**Important:** 0.85 was set for OpenAI embeddings in the original spec.
Since this uses a different (free, self-hosted) model, re-calibrate the
threshold against a labeled sample of known-duplicate vs. known-distinct
reports before relying on it in production — different embedding models
score similarity on different scales.

## Integration boundaries
- D1 spam filtering remains upstream; this service accepts the resulting
   `IncomingTicket` payload.
- Authentication, authorization, CORS, rate limiting, and production logging
   belong in the integrating gateway or backend.
- Track A and Track B dispatch remain downstream of the persisted operator
   decision; see the root `INTEGRATION_README.md` for the recommended outbox
   extension.

## G1 Priority Scorer

The service now recalculates `active_tickets.priority_score` after every D2 merge/create.

Formula:

`(severity * W1) + (cluster_count * W2) + (age_in_hours * W3) + (population_impact * W4)`

Weights are configured through `.env` (`PRIORITY_*_WEIGHT`). Defaults are `1.0, 1.0, 0.1, 1.0`.

Endpoints:
- `POST /g1/recalculate/{ticket_id}` — recalculate one ticket.
- `POST /g1/recalculate` — recalculate all active tickets.

Run the focused tests from the project root:

```powershell
python -m pytest -q tests
```

## DNO Human Validation Gate

Run the appended `validation_decisions` migration in `schema.sql`.

- `GET /dno/tickets?limit=50&offset=0` — active tickets ordered by `priority_score` descending, including the D4 `suggested_track`.
- `GET /dno/tickets/{ticket_id}` — fetch one active ticket for the dashboard.
- `POST /dno/tickets/{ticket_id}/decision` — persist an operator decision and remove the ticket from the active queue.

Decision body:

```json
{"decision":"track_a","operator_id":"operator-1","notes":"Validated road obstruction"}
```

Allowed decisions are `track_a`, `track_b`, and `reject_merge`. Track A/Track B set the ticket status to `validated`; Reject-Merge sets it to `merged`. Every decision is recorded in `validation_decisions`.
