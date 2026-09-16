# Agent_D Integration Guide

This guide explains how to integrate the Agent_D D2 + G1 + DNO Human Validation Gate service into an existing backend, dashboard, and database.

## 1. What this service provides

The service exposes:

- `POST /d2/ingest` — accepts a D1-filtered ticket and performs geospatial + semantic deduplication.
- `POST /g1/recalculate/{ticket_id}` — recalculates one ticket's priority score.
- `POST /g1/recalculate` — recalculates all active tickets.
- `GET /dno/tickets` — returns active tickets ordered by priority for the dashboard.
- `GET /dno/tickets/{ticket_id}` — returns one active ticket and its suggested research track.
- `POST /dno/tickets/{ticket_id}/decision` — stores the operator decision and removes the ticket from the active queue.
- `GET /health` — basic service health check.

The DNO endpoints are designed to be called by a dashboard or an API gateway. Authentication, authorization, CORS, rate limiting, and production logging should be added by the integrating application or gateway.

## 2. Project layout

```text
Triage and route/
├── app/
│   ├── main.py          # FastAPI routes
│   ├── db.py            # SQLAlchemy database session
│   ├── config.py        # Environment configuration
│   ├── schemas.py       # Request/response models
│   ├── validation.py    # DNO ticket feed and decisions
│   ├── priority.py      # G1 priority scoring
│   ├── dedup.py         # D2 deduplication
│   └── embedding.py     # all-MiniLM-L6-v2 model
├── schema.sql           # Database schema and validation audit table
├── requirements.txt
├── .env.example
└── INTEGRATION_README.md
```

## 3. Prerequisites

- Python 3.10 or newer
- PostgreSQL 16 recommended
- PostGIS extension
- pgvector extension
- A database user with permission to create tables, indexes, and extensions

The easiest local database option is the included Docker Compose setup. It
builds on the pgvector image and adds PostGIS, because the upstream pgvector
image does not include PostGIS:

```powershell
cd "Triage and route"
docker compose up -d --build
```

## 4. Install and configure

From the project root:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the database connection. Example:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/dno_triage
GEO_RADIUS_METERS=100
SIMILARITY_MERGE_THRESHOLD=0.85
GEO_CANDIDATE_LIMIT=25
PRIORITY_SEVERITY_WEIGHT=1.0
PRIORITY_CLUSTER_SIZE_WEIGHT=1.0
PRIORITY_AGE_HOURS_WEIGHT=0.1
PRIORITY_POPULATION_WEIGHT=1.0
```

Apply the schema:

```bash
psql "$DATABASE_URL" -f schema.sql
```

On Windows PowerShell, use the connection string directly if the `$DATABASE_URL` environment variable is not set:

```powershell
psql "postgresql://postgres:postgres@localhost:5432/dno_triage" -f schema.sql
```

## 5. Start the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the generated API documentation:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/health`

The embedding model may download on first startup. Allow additional startup time on the first run.

## 6. Integration flow

```text
D1 middleware
    │
    ├── rejected ticket ──> cold_storage
    │
    └── accepted ticket
            │
            ▼
       POST /d2/ingest
            │
            ▼
       active_tickets
            │
            ▼
       G1 priority_score
            │
            ▼
       GET /dno/tickets
            │
            ▼
       Dashboard operator review
            │
            ├── track_a
            ├── track_b
            └── reject_merge
                    │
                    ▼
           POST /dno/tickets/{id}/decision
                    │
                    ▼
          validation_decisions + status update
```

## 7. Dashboard integration

### Load the queue

```javascript
const response = await fetch(
  `${API_BASE_URL}/dno/tickets?limit=50&offset=0`
);

if (!response.ok) {
  throw new Error(`Unable to load tickets: ${response.status}`);
}

const page = await response.json();
renderTickets(page.items);
```

The response has this shape:

```json
{
  "items": [
    {
      "ticket_id": 42,
      "master_ticket_id": null,
      "problem_statement": "Large pothole near the school entrance",
      "domain": "ROADS",
      "urgency": "HIGH",
      "severity": 4,
      "population_impact": 3,
      "status": "active",
      "cluster_count": 7,
      "priority_score": 12.4,
      "created_at": "2026-09-15T10:00:00+00:00",
      "updated_at": "2026-09-15T10:10:00+00:00",
      "suggested_track": "track_a"
    }
  ],
  "limit": 50,
  "offset": 0
}
```

### Display the suggested route

- `track_a`: show “Track A — Roads/Waste”.
- `track_b`: show “Track B — Innovation/HEI Registry”.
- `review_required`: show “Manual classification required”.

The suggestion is not the final operator decision. The operator must explicitly select a decision.

### Submit a decision

```javascript
async function submitDecision(ticketId, decision, notes) {
  const response = await fetch(
    `${API_BASE_URL}/dno/tickets/${ticketId}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision,
        operator_id: currentUser.id,
        notes
      })
    }
  );

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.detail || "Decision failed");
  }

  return body;
}
```

Allowed values:

```text
track_a
track_b
reject_merge
```

Recommended UI behavior after a successful response:

1. Remove the ticket from the active queue.
2. Show a success notification.
3. Refresh the current page or request the next ticket.
4. Keep the returned decision record in the client audit view if needed.

## 8. API examples with curl

Health check:

```bash
curl http://localhost:8000/health
```

List prioritized tickets:

```bash
curl "http://localhost:8000/dno/tickets?limit=20&offset=0"
```

Get one ticket:

```bash
curl http://localhost:8000/dno/tickets/42
```

Submit Track A:

```bash
curl -X POST http://localhost:8000/dno/tickets/42/decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "track_a",
    "operator_id": "operator-1",
    "notes": "Validated road obstruction"
  }'
```

Submit Track B:

```bash
curl -X POST http://localhost:8000/dno/tickets/43/decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "track_b",
    "operator_id": "operator-1",
    "notes": "Requires research review"
  }'
```

Reject or merge:

```bash
curl -X POST http://localhost:8000/dno/tickets/44/decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "reject_merge",
    "operator_id": "operator-1",
    "notes": "Duplicate of an existing issue"
  }'
```

## 9. Status and audit behavior

When an operator submits a decision:

- `track_a` changes the ticket status to `validated`.
- `track_b` changes the ticket status to `validated`.
- `reject_merge` changes the ticket status to `merged`.
- Every decision is inserted into `validation_decisions`.
- The ticket is removed from the active dashboard queue because the queue only selects `status = 'active'`.

The decision operation locks the ticket row with `FOR UPDATE`, which prevents two concurrent operators from successfully deciding the same active ticket. A second decision receives HTTP `409` after the first transaction changes the status.

## 10. Suggested production gateway

Do not expose the FastAPI service directly to the public internet without protection. Put it behind your existing API gateway or backend-for-frontend:

```text
Browser dashboard
       │
       ▼
Authenticated gateway / backend
       │
       ├── verifies user session or JWT
       ├── checks operator permissions
       ├── adds operator_id from the authenticated user
       ├── forwards allowed requests
       └── records request logs
       │
       ▼
Agent_D FastAPI service
       │
       ▼
PostgreSQL
```

The backend should not trust an arbitrary `operator_id` supplied by the browser. Prefer deriving it from the authenticated session and either removing the client field or validating it against the logged-in user.

## 11. Integration checklist

- [ ] Configure PostgreSQL with PostGIS and pgvector.
- [ ] Apply `schema.sql`.
- [ ] Configure `.env` and verify `DATABASE_URL`.
- [ ] Start the API and confirm `/health` returns `{"status":"ok"}`.
- [ ] Connect the dashboard queue to `GET /dno/tickets`.
- [ ] Display `priority_score`, `cluster_count`, domain, urgency, and `suggested_track`.
- [ ] Add Track A, Track B, and Reject-Merge controls.
- [ ] Send decisions to `POST /dno/tickets/{ticket_id}/decision`.
- [ ] Handle HTTP `404`, `409`, and validation errors in the UI.
- [ ] Add authentication and operator authorization.
- [ ] Add CORS configuration if the dashboard is hosted on another origin.
- [ ] Add integration tests against a test PostgreSQL database.
- [ ] Recalibrate the D2 similarity threshold before production use.

## 12. Important current limitations

- The D4 classification rules are deterministic and currently classify only the configured domain groups.
- `review_required` is returned for unknown or missing domains.
- The service does not currently implement authentication, role-based access control, or an external Track A/Track B dispatch system.
- The dashboard must refresh its queue after a decision because the selected ticket is no longer active.
- The schema uses a self-referencing `master_ticket_id`; preserve this relationship when integrating with other ticket systems.
- The current decision endpoint records the decision and updates status, but it does not call an external research registry or dispatch API. Add that integration after the operator decision is persisted, preferably through an asynchronous job or outbox pattern.

## 13. Recommended next extension: dispatch after validation

For production, add a separate dispatch layer after the decision is saved:

```text
POST /dno/tickets/{id}/decision
          │
          ▼
validation_decisions
          │
          ▼
outbox event: ticket.validated
          │
          ▼
Track A or Track B dispatcher
          │
          ▼
External research / registry API
```

This prevents a slow or unavailable external system from blocking the operator's decision and gives the project a reliable retry mechanism.
