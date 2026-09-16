# 5. ULB Dispatch (Track A)

Implements Subgraph TA (TA1/TA2/TA3) from the SAHYOG architecture: once a
human operator marks a ticket `track_a` in `3.Triage and route` (Agent D),
this service routes it to the correct Urban Local Body (ULB) department,
dispatches it via API or email, tracks SLA/escalation, and verifies closure
proof. Runs on **port 8004**.

```
citizen report -> 1.Language normalizer -> 2.Evidence Extractor
    -> 3.Triage and route (dedup, priority, D4 human validation)
        -> [decision == track_a] -> 5.ULB Dispatch (this service)
            -> ULB contact (api/email) -> officer status link -> closure proof
```

## Setup

1. Same Postgres instance as `3.Triage and route` (PostGIS already enabled
   there). This service owns its own tables in that same database — it does
   **not** create or require a separate database.
2. Apply the base schema (if not already applied) and this service's
   migration, in order, from `3.Triage and route/`:
   ```bash
   psql "$DATABASE_URL" -f schema.sql
   psql "$DATABASE_URL" -f schema_002_dispatch_hook.sql
   ```
   Like `schema.sql`, this migration is **not** auto-applied by either
   service at startup — run it manually once. It is additive-only
   (`CREATE TABLE/INDEX IF NOT EXISTS`) and safe to re-run.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in `INTERNAL_SERVICE_TOKEN` and
   `ADMIN_FORM_PASSWORD` at minimum (see "Manual cross-service setup" below).
5. Run the service:
   ```bash
   uvicorn app.main:app --port 8004
   ```
   With default env settings this alone is enough to reach a fully
   dispatch-ready system — no manual SQL beyond step 2, no admin-form step
   required first. See "Hackathon fast-path defaults" below.

## Manual cross-service setup: `INTERNAL_SERVICE_TOKEN`

`3.Triage and route/app/validation.py`'s `apply_operator_decision` fires a
non-blocking webhook to this service's `POST /dispatch/{ticket_id}` whenever
an operator records `decision == "track_a"`. That webhook authenticates with
an `X-Internal-Token` header.

**Both services must define the same `INTERNAL_SERVICE_TOKEN` value in
their own `.env` file** — it is not passed between them at runtime, it is
configured twice. A mismatch fails silently from the webhook's perspective
(it's wrapped in `try/except: pass` so a Dispatch outage never blocks the
validation decision) and only surfaces later via `POST /dispatch/reconcile`
picking up the "missed" ticket. **If Track A dispatches never seem to fire
immediately, check this token match first** before anything else.

Optional: set `ULB_DISPATCH_BASE_URL` in `3.Triage and route/.env` if this
service runs on a different host/port than the default
`http://localhost:8004`.

## Reconciliation safety net (why a missed webhook is never data loss)

The Step 6 webhook call is fire-and-forget by design — it must never block
or fail the DNO validation decision itself. To make that safe, this service
independently reconciles:

```
POST /dispatch/reconcile
```

which scans `validation_decisions` for `decision='track_a'` rows with no
matching row in `dispatches` (a `LEFT JOIN ... IS NULL`) and dispatches each
one via the same logic as `POST /dispatch/{ticket_id}`. It's safe to call
repeatedly/concurrently (see `uq_dispatches_ticket_active` below) and is
meant to be called periodically by `worker.py` (or the in-process background
loop — see below) **and** safe to trigger manually or via cron as a manual
fallback.

## Idempotency under concurrency

`uq_dispatches_ticket_active` (a partial unique index on
`dispatches(ticket_id) WHERE status NOT IN ('resolved','disputed')`) is the
**real** guarantee against two active dispatches for the same ticket. The
application-level "does an active dispatch already exist?" check in
`dispatch.py` is a courtesy fast path only — under a genuine race (the
webhook and a `reconcile` sweep landing at the same moment), the second
INSERT hits that constraint, and the code catches the resulting
`IntegrityError`, rolls back, and returns the winning row instead of
raising or creating a duplicate.

## Hackathon fast-path defaults

Three env-controlled defaults exist purely to collapse setup time for a
demo. Each is independently toggleable and each has an explicit path back
to "real" production behavior:

| Setting | Default | What it does | Flip to |
|---|---|---|---|
| `SEED_DEMO_DATA` | `true` | On startup, if `ulb_directory` is empty, auto-inserts one demo ULB (`DEMO_ULB_BOUNDARY_WKT`) + one catch-all contact (`DEMO_CONTACT_EMAIL`, pre-verified) | `false` — no auto-seed; populate via `/admin/onboard` or real data instead |
| `EMAIL_DRY_RUN` | `true` | `email_adapter.py` builds the full email but logs it into `dispatch_events` instead of calling `smtplib` | `false` — real SMTP send, needs real `SMTP_*` values |
| `RUN_BACKGROUND_LOOP_IN_PROCESS` | `true` | SLA scan + inbox poll + reconcile run as an `asyncio` task inside the FastAPI app — `uvicorn app.main:app` alone is a complete system | `false` — run `python worker.py` as a separate process instead |

Flipping all three to their non-default value gets you exactly the
production-shaped behavior this service was designed for (real SMTP,
separate worker process, no auto-seeded data). None of these defaults were
"wrong" designs — they're purely there to make `uvicorn app.main:app
--port 8004` alone a fully working demo immediately after the migration.

**The actual hackathon smoke test:** with default settings, applying only
the two `psql -f` migrations and then running `uvicorn app.main:app --port
8004` (one process, no other manual steps) is enough for
`POST /dispatch/{ticket_id}` to succeed and produce a dry-run `sent`
`dispatch_events` row. This is asserted in
`tests/test_hackathon_smoke.py`.

## ULB data reality

`ulb_contacts` is intended to be populated **live**, via the self-service
onboarding form below — not pre-loaded from scraped data:

```
GET  /admin/onboard   -- HTML form (no build step, no JS framework)
POST /admin/onboard   -- inserts a new ulb_contacts row
```

Protected by HTTP Basic auth checked against `ADMIN_FORM_PASSWORD` — a
**separate** secret from `INTERNAL_SERVICE_TOKEN` (different trust
boundary: a human filling out a form vs. service-to-service calls).

In practice, real ULB contact data (confirmed against Jharkhand's Urban
Development & Housing Department listings) is almost always a single
generic office email per ULB, not department-specific ones. That means:

- `domain` will be `NULL` (a catch-all contact) for most rows, until/unless
  an officer self-registers a specific department's contact. `router.py`'s
  `resolve_contacts()` treats the catch-all branch as the **common case**,
  not an edge case — it's exercised by most real dispatches, not a fallback
  for rare gaps.
- **`verified_at` is currently trust-on-registration**, not a security
  control: submitting the onboarding form sets `verified_at = now()`
  immediately. `# TODO(human):` before any real deployment, replace this
  with an actual verification step (e.g. OTP to `officer_phone`, or a
  signed link sent to a `.gov.in` email) — `closure.py`'s
  `verify_closure()` treats `verified_at` as a trust signal for
  auto-resolving tickets, so an unverified contact should not be trusted
  for that.

## Endpoints

**Internal only** (require `X-Internal-Token` header matching
`INTERNAL_SERVICE_TOKEN`; return `401` with a JSON body if missing/wrong).
**Must never be reachable from the public internet in deployment** — this
is a network/firewall requirement, not just an app-level check:

- `POST /dispatch/reconcile` — safety-net sweep, see above.
- `POST /dispatch/{ticket_id}` — idempotent dispatch trigger (called by the
  Step 6 webhook, or manually/via reconcile).
- `GET /dispatch/{ticket_id}` — current dispatch + full event history, for
  internal ops/status-portal consumption.

**Public by design** (the token/password itself is the credential — no
`X-Internal-Token` check applies to these):

- `GET /status/{token}` / `POST /status/{token}/update` — one-time officer
  status-link page (acknowledge / in-progress / resolved-with-photo).
  Rejects oversized (`MAX_CLOSURE_PHOTO_MB`) or non-image uploads by
  checking actual file signature bytes, not the client-supplied
  content-type header.
- `GET /admin/onboard` / `POST /admin/onboard` — protected by HTTP Basic
  auth (`ADMIN_FORM_PASSWORD`), a different trust boundary from the
  internal-token routes above.

## Circuit breaker (API → email auto-demotion)

If 3 consecutive `api_error` events land against the same `contact_id`,
subsequent dispatches to that contact demote to the ULB's email-channel
contact at the same level/domain, if one exists in the same
`resolve_contacts()` result set. If no email contact exists, the failure is
logged (`event_type='api_error'`, explanatory `payload`) and flagged for
human ops review rather than silently dropped.

## SLA / escalation

Business-hours math is computed in **Asia/Kolkata explicitly** — all
`TIMESTAMPTZ` columns are stored in UTC, and the deployment server's local
timezone is not guaranteed to be IST. Sat/Sun are excluded;
`# TODO(human):` plug in a real public-holiday calendar (out of scope for
this MVP). Escalation SLA hours live in `escalation_matrix`, seeded by
`schema_002_dispatch_hook.sql` with placeholder defaults —
`# TODO(human):` confirm against actual Right-to-Service Act timelines for
your state before relying on them in production.

The escalation path calls the **same** `router.resolve_contacts()` the
initial-dispatch path uses (not a separate hand-rolled query), so the
domain → catch-all fallback logic lives in exactly one place.

## Closure verification

`closure.py`'s `verify_closure()` never auto-rejects or auto-approves on
ambiguous signals — a `closure_proofs` row is always inserted for a
complete, honest audit trail. Auto-resolve only happens when: submitted by
a verified officer, the geo check passes (haversine distance to the
ticket's location within `CLOSURE_GEO_RADIUS_METERS`), and the vision
similarity check (if configured) doesn't contradict it.

`VISION_CLASSIFIER_URL` optionally reuses `2.Evidence Extractor`'s C3
vision endpoint. `# TODO(human):` confirm the exact request/response shape
against that service's actual `/evidence/attach-photo` contract before
relying on this in production — the *semantics* also need a human decision
(that endpoint was built to verify a new complaint's photo, not judge
whether a resolved-issue photo shows the issue is actually gone). Leave
`VISION_CLASSIFIER_URL` blank to skip auto visual verification entirely and
require manual review instead.

## Known limitations

- **Single demo ULB boundary.** The seeded/demo `ulb_directory` row is a
  wide bounding box, not a real municipal boundary. `# TODO(human):`
  replace with real per-ULB boundary polygons before handling more than one
  municipality — the routing logic itself does not need to change, only
  the seed data.
- **No holiday calendar** in SLA business-hours math (Sat/Sun only).
- **Generic API adapter payload.** No real ULB API schema was known at
  build time; `api_adapter.py`'s payload shape is a documented placeholder.
  `# TODO(human):` each real ULB API will likely need its own payload
  adapter subclass.
- **No ULB-facing translations.** Outbound emails/status-link pages are
  English-only in this MVP (the underlying `standardized_problem_statement`
  is already English-normalized upstream). `# TODO(human):` add regional
  translations to the `EMAIL_TEMPLATES` dict in `email_adapter.py` if a
  state requires officer communication in the regional language.
- **No LLM-based reply-intent parsing.** `inbox_poller.py` matches replies
  to dispatches by correlation code and logs the raw body for human review;
  it does not attempt to infer "resolved"/"disputed" from free text. Marked
  as a future enhancement in that file.
- **Trust-on-registration for `/admin/onboard`.** See "ULB data reality"
  above — must be replaced with real verification before production.
- **Synchronous retry/backoff in `dispatch.py`.** MVP-simple
  (`time.sleep`-based), not a task queue. Fine for hackathon load; a real
  deployment should move retries to a proper task queue.

## Tests

```bash
pytest -q
```

All tests run against a mocked DB session (no live Postgres required),
mirroring the style of `3.Triage and route/tests/test_agent_d_integration.py`.
Covers: `router.resolve_contacts` (exact/ambiguous/missing/catch-all-fallback
cases), `dispatch.py`'s idempotency + correlation-code-collision +
circuit-breaker logic, `sla.py`'s Asia/Kolkata business-hours math (with a
test that would fail under naive/UTC time), `closure.py`'s geo-check
branching, internal-token auth enforcement, public status-link routes
correctly *not* requiring that token, closure-photo upload validation by
file signature, and the hackathon smoke-test path described above.
