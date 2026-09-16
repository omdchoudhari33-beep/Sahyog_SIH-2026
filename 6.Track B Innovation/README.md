# 6. Track B Innovation

Implements subgraph TB from the SAHYOG architecture (R1 HEI Capability Registry, TB1
semantic HEI matcher, TB2 accept/decline with auto-re-route, TB3 team formation, TB4
proposal submission → nodal approval). Runs on **port 8006**.

```
3.Triage and route (D4 human validation gate, decision == "track_b")
    -> POST /trackb/{ticket_id}  (this service, fire-and-forget webhook)
        -> TB1 matches ticket against hei_capabilities by cosine similarity
        -> TB2 notifies the best-match HEI; decline -> next-best HEI (up to
           MAX_HEI_MATCH_ATTEMPTS), accept -> TB3 team formation
        -> TB4 proposal submission -> nodal officer approves/rejects/requests revision
            -> on approval: fire-and-forget webhook to 7.Industry Partnership
               and 8.Lifecycle Outcome
```

## Setup

1. Same Postgres instance/DB as `3.Triage and route` and `5.ULB Dispatch` - this
   service owns its own tables there, does not create a separate database.
2. Apply this service's migration (additive-only, safe to re-run):
   ```bash
   psql "$DATABASE_URL" -f schema.sql
   ```
   Not auto-run by any service at startup - same convention as every other migration
   in this repo.
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`. **`INTERNAL_SERVICE_TOKEN` must be the exact same
   value already configured for `3.Triage and route` ↔ `5.ULB Dispatch`** - this repo
   treats it as one shared internal-services secret, not a new one per service pair.
5. `uvicorn app.main:app --port 8006`

With default settings (`SEED_DEMO_DATA=true`, `EMAIL_DRY_RUN=true`) this alone is
enough to reach a dispatch-ready system: one demo HEI + one capability (with a real
computed embedding) auto-seed on startup.

## Manual cross-service setup

`3.Triage and route/app/validation.py`'s `apply_operator_decision` fires a
non-blocking webhook to `POST /trackb/{ticket_id}` whenever an operator records
`decision == "track_b"` - the exact same shape as the existing `track_a` → 
`5.ULB Dispatch` webhook, reusing the same `INTERNAL_SERVICE_TOKEN`. A mismatch fails
silently from the webhook's perspective (wrapped in `try/except: pass`) and only
surfaces later via `POST /trackb/reconcile` picking up the "missed" ticket.

Optional: set `TRACKB_BASE_URL` in `3.Triage and route/.env` if this service runs on
a different host/port than `http://localhost:8006`.

## Reconciliation safety net

`POST /trackb/reconcile` scans `validation_decisions` for `decision='track_b'` rows
with no matching row in `hei_matches` at all (first-ever attempt) and matches each
one - the same LEFT JOIN pattern as `5.ULB Dispatch/app/dispatch.py`'s `reconcile()`.
Verified live: it correctly picked up two `track_b` decisions from earlier test data
that predated this service even existing.

## Idempotency under concurrency

`uq_hei_matches_ticket_active` (partial unique index on `hei_matches(ticket_id) WHERE
status = 'proposed'`) is the real guarantee against two concurrently-active matches for
the same ticket - the application-level check in `matcher.py` is a courtesy fast path
only, exactly mirroring `5.ULB Dispatch`'s `uq_dispatches_ticket_active` design.

## Semantic matching (TB1)

Reuses `3.Triage and route`'s exact embedding setup (`all-MiniLM-L6-v2`, 384-dim,
pgvector cosine `<=>` operator) - but the ticket side of the match needs **no new
embedding call**: it reads `active_tickets.embedding`, already computed by Agent3,
directly. Only HEI *capability* descriptions get embedded, once, at onboarding time
(admin-only, not on the hot path).

Capacity is enforced (a simplification): an HEI capability is only offered a new match
if its count of currently-`accepted` matches is below `hei_registry.capacity_active_projects`
- in-flight `proposed` matches don't count against capacity yet.

## Decline → re-route (TB2)

Declining a match automatically creates a new match against the next-best HEI
capability (excluding all HEIs already declined for this ticket), up to
`MAX_HEI_MATCH_ATTEMPTS`. Beyond that, the ticket is left with no active match and
flagged in the response detail for human ops review - `# TODO(human)`: once
`9.Transparency Layer`'s audit log is wired into this service, route that flag there
instead of only into the HTTP response.

## Endpoints

**Internal only** (`X-Internal-Token` header, `401` if missing/wrong; must never be
reachable from the public internet in deployment):
- `POST /trackb/reconcile`, `POST /trackb/{ticket_id}`, `GET /trackb/{ticket_id}`

**Public** (token/password is the credential):
- `GET /hei/{token}` / `POST /hei/{token}/decide` / `POST /hei/{token}/team` /
  `POST /hei/{token}/proposal` - the HEI's entire accept → team → proposal flow,
  server-rendered, no build step, no JS framework (mirrors `5.ULB Dispatch`'s
  `/status/{token}` pattern).
- `GET/POST /admin/onboard-hei`, `GET/POST /admin/nodal-review[/{id}]` - `HTTPBasic`
  via `ADMIN_FORM_PASSWORD` (a separate trust boundary from `INTERNAL_SERVICE_TOKEN`,
  same separation `5.ULB Dispatch` uses).

## Known limitations / TODO(human)

- **HEI decline-exhaustion has no persistent ops-review queue yet** - it's only
  visible in the API response and this service's logs until `9.Transparency Layer`'s
  audit log is wired in (deferred by design, see root integration plan).
- **Capacity check is `accepted`-only**, not counting in-flight proposals - fine for
  hackathon scope, would need tightening before real multi-tenant load.
- **No real per-HEI verification flow** - onboarding is trust-on-registration, same
  hackathon shortcut already used (and already flagged) in `5.ULB Dispatch`.
- **`INDUSTRY_PARTNERSHIP_BASE_URL` / `LIFECYCLE_OUTCOME_BASE_URL` webhooks** on
  proposal approval will silently no-op until those two services exist and are
  running - by design (fire-and-forget, non-blocking), not a bug.

## Tests

```bash
pytest -q
```
Mocked-DB only, no live Postgres required - same convention as `5.ULB Dispatch`.
