# 9. Transparency Layer

Implements subgraph X from the SAHYOG architecture (X1 Govt Analytics Dashboard, X2
Citizen Status Portal, X3 Immutable Audit Log). Runs on **port 8009**.

Unlike the other three new services, this one is mostly read-only aggregation across
every other service's tables (same DB instance), plus one write-only ingestion
endpoint that the others call into.

## Setup

1. Same Postgres instance/DB as every other service. Built and applied **last**,
   since its dashboard/status queries assume services 3, 5, 6, 7, 8's tables all
   exist.
2. `psql "$DATABASE_URL" -f schema.sql` (additive-only, not auto-run at startup).
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`. `INTERNAL_SERVICE_TOKEN` must be the exact same
   repo-wide value used everywhere else - it only gates `POST /audit/log`; the X1/X2
   read endpoints are intentionally public.
5. `uvicorn app.main:app --port 8009`

## X3 Immutable Audit Log - live in services 6, 7, 8

`POST /audit/log` is called (fire-and-forget, non-blocking, same pattern as every
other cross-service call in this repo) from:

- `6.Track B Innovation/app/matcher.py` on every HEI match created
- `6.Track B Innovation/app/teams.py` on every nodal approve/reject/revision decision
- `7.Industry Partnership/app/funding.py` on every milestone fund release
- `8.Lifecycle Outcome/app/disposition.py` on every handover/spin-out disposition

**Verified live**: a fresh `track_b` decision through the running pipeline produced a
real `hei_matched` audit row with zero manual intervention.

**Deliberately not wired into services 1, 2, 3, 4, 5** in this pass - see the root
integration plan. Adding it there is a small, mechanical, identical-pattern follow-up
(one more fire-and-forget POST per service), left as a deliberate follow-up rather
than bundled silently into already-shipped, tested files.

**What "immutable" means here**: this app never exposes an `UPDATE` or `DELETE` route
for `audit_log`, and no code path in this service issues either. That is an honesty
guarantee, not a cryptographic one. `# TODO(human)`: for genuine tamper-evidence
before any real deployment, add a `REVOKE UPDATE, DELETE` grant on this table for the
application's DB role, and/or a hash-chain column (`prev_hash`/`this_hash`).

## X1 Govt Analytics Dashboard

`GET /transparency/dashboard` (HTML, public) / `GET /transparency/dashboard.json`
(raw JSON). Real aggregate SQL, not placeholder numbers:

- **District × domain heatmap**: spatial join (`ST_Contains`) between `active_tickets.geom`
  and `5.ULB Dispatch`'s `ulb_directory.district`.
- **HEI participation**: counts from `6.Track B Innovation`'s `hei_matches`.
- **Industry engagement**: counts and total committed amount from
  `7.Industry Partnership`'s `partnership_matches` / `milestone_fund_ledger`.
- **Completion rate**: pass/fail/pending ratio from `8.Lifecycle Outcome`'s
  `pilot_validations`.
- **Outcomes**: handover/spin-out counts plus Track A resolved-dispatch count from
  `5.ULB Dispatch`'s `dispatches`.

A real bug was caught and fixed while building this: an earlier draft of
`industry_engagement()` used `FULL OUTER JOIN milestone_fund_ledger ON true`, which
is a cartesian product that would have multiplied `total_committed_amount` by the
row count of the other table. Fixed to independent scalar subqueries instead, with a
regression test (`tests/test_dashboard.py`) asserting a single query execution.

## X2 Citizen Status Portal

`GET /status/{ticket_id}` (HTML, public) / `GET /status/{ticket_id}.json`. The ticket
ID **is** the lookup key - not a secret token like the officer/HEI/partner status
links elsewhere in this repo. That's safe here because these responses only ever
return status/progress fields (domain, status, problem statement, track, milestone
titles/status, dispatch status) - never contact details, internal routing data, or
anything else worth protecting behind a secret.

Works for **either** track - reads `5.ULB Dispatch`'s `dispatches` for Track A, or
`6.Track B Innovation`'s `hei_matches`/`proposals` plus `8.Lifecycle Outcome`'s
`milestones`/`pilot_validations` for Track B - and returns a single unified timeline.
**Verified live** against real tickets from both tracks created during this session's
testing.

`# TODO(human)`: real SMS/WhatsApp *delivery* of this link. This service only serves
the lookup page itself - the architecture diagram's "ticket ID + SMS/WhatsApp" is the
citizen's channel for *finding* this page, not something this service proactively
sends yet.

A real bug was also caught and fixed here during live testing: `validation_decisions`
has a `created_at` column, not `decided_at` - an earlier draft's SQL referenced a
column that doesn't exist and 500'd on every ticket with a recorded decision. Fixed,
with a regression test.

## Endpoints

**Internal only** (`X-Internal-Token`, `401` if missing/wrong): `POST /audit/log`.

**Public** (no auth by design - see X1/X2 sections above for why):
`GET /transparency/dashboard[.json]`, `GET /status/{ticket_id}[.json]`.

## Known limitations / TODO(human)

- Audit log immutability is an honesty guarantee, not a DB-enforced or cryptographic
  one (see X3 section above).
- Not wired into services 1-5 yet (deliberate, see X3 section above).
- No real SMS/WhatsApp push for X2 (deliberate, see X2 section above).
- Dashboard queries assume every other service's migration has been applied; if one
  hasn't, the relevant section of `full_dashboard()` will raise rather than degrade
  gracefully - acceptable for this MVP since this service is meant to be stood up
  last, but worth hardening (e.g. per-section try/except) before a deployment where
  services might be added incrementally over time.

## Tests

```bash
pytest -q
```
Mocked-DB only, no live Postgres required.
