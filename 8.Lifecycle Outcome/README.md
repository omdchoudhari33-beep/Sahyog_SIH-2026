# 8. Lifecycle Outcome

Implements subgraph F from the SAHYOG architecture (F1 Milestone Tracker + Evaluator,
F2 Pilot Validation, F3 Handover to ULB/Panchayat, F4 Startup/Incubation Spin-out).
Runs on **port 8008**.

```
6.Track B Innovation (nodal officer approves a proposal)
    -> POST /lifecycle/proposal-approved/{proposal_id}  (this service, fire-and-forget webhook)
        -> F1 initializes 3 milestones from the proposal's declared timeline
        -> a human evaluator scores each milestone as it completes
        -> F2 pilot validation (geo-check + optional vision hook) on a closure photo
        -> a human decides the disposition: F3 handover to ULB (reuses the
           ALREADY-BUILT 5.ULB Dispatch /dispatch/{ticket_id} - no reinvented
           ULB contact routing) and/or F4 startup spin-out
```

## Setup

1. Same Postgres instance/DB as the other services, and the same MinIO
   object storage the other services use (see `../DATABASE.md`).
2. `psql "$DATABASE_URL" -f schema.sql` (additive-only, not auto-run at startup).
3. `psql "$DATABASE_URL" -f schema_002_pilot_media.sql` - requires
   `3.Triage and route/schema_003_media_objects.sql` to have been applied
   first (adds `pilot_validations.photo_media_id`).
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env`. `INTERNAL_SERVICE_TOKEN` must be the exact same
   repo-wide value used by every other service. `S3_*` vars point pilot
   validation photo uploads at MinIO instead of the old local
   `pilot_uploads/` disk folder.
6. `uvicorn app.main:app --port 8008`

No demo-seed here (unlike the other services) - there's no standalone registry to
seed; milestones only ever come from a real approved Track B proposal.

## Manual cross-service setup

`6.Track B Innovation/app/teams.py`'s `nodal_decide()` fires a non-blocking webhook
here on proposal approval (same call as to `7.Industry Partnership`), reusing the
shared `INTERNAL_SERVICE_TOKEN`. Set `LIFECYCLE_OUTCOME_BASE_URL` in that service's
`.env` if this one runs elsewhere.

`ULB_DISPATCH_BASE_URL` must point at a *running* `5.ULB Dispatch` for F3 handover to
actually create a dispatch - if it's unreachable, the handover record is still saved
(with `ulb_dispatch_id = NULL`) rather than failing the human's action, but the ULB
never actually gets notified until that service is back up. There's no reconcile
sweep for handover specifically (unlike the webhook patterns elsewhere) since it's a
direct, synchronous human action, not a fire-and-forget async trigger.

## Reconciliation safety net

`POST /lifecycle/reconcile` scans `proposals` for `status='approved'` rows with no
`milestones` row at all, and initializes each one. **Verified live**: on first
startup it correctly picked up a proposal approved before this service existed.

## F2 Pilot Validation - never auto-resolves on ambiguous signals

Same honesty rule as `5.ULB Dispatch/app/closure.py`: `verdict` is `'pass'` only when
the geo-check passes and vision either agrees or was skipped; `'fail'` only when the
geo-check explicitly fails; otherwise `'pending_review'` - it never guesses. Every
validation is recorded (a real audit trail) regardless of outcome, and a pass/fail
verdict also writes an `rd_outcome_feedback` row - the diagram's "resolution outcome
retrains classifier" signal. `# TODO(human)`: the actual retraining job that reads
this table doesn't exist yet; recording the signal does.

## F3/F4 disposition is a human decision, never auto-inferred

A pilot pass does **not** automatically trigger handover or spin-out - a human calls
`POST /admin/{ticket_id}/disposition` with an explicit `handover` / `spinout` / `both`
choice. This mirrors the "AI assisting, not deciding" principle already stated in
`4.Orchestrator/README.md` for the conversational flow.

## Endpoints

**Internal only** (`X-Internal-Token`, `401` if missing/wrong):
`POST /lifecycle/reconcile`, `POST /lifecycle/proposal-approved/{proposal_id}`,
`GET /lifecycle/{ticket_id}`.

**Admin** (`HTTPBasic` via `ADMIN_FORM_PASSWORD` - human-operator actions, a
different trust boundary from `INTERNAL_SERVICE_TOKEN`; there is no public
token-link flow in this service, unlike the other three, since there's no citizen-
or-partner-facing step here, only officer/evaluator actions):
`POST /admin/milestones/{id}/evaluate`, `POST /admin/{ticket_id}/pilot-validate`
(photo upload, rejects oversized/non-image files by actual file signature, same rule
as `5.ULB Dispatch`), `POST /admin/{ticket_id}/disposition`.

## Known limitations / TODO(human)

- **Milestone plan is a fixed 3-step template** (Kickoff / Mid-point / Final) spaced
  off `proposals.timeline_weeks` - real projects will need more flexible milestone
  planning.
- **`EVALUATION_PASS_THRESHOLD = 0.6`** is a placeholder cutoff, not calibrated
  against real evaluator data - flagged in code with the same caveat
  `3.Triage and route`'s own free-chosen `SIMILARITY_MERGE_THRESHOLD` carries.
- **No real public holiday calendar or evaluator-reminder system** for milestone
  target dates - out of scope for this MVP.
- Vision-classifier hook for pilot validation carries the same
  contract-confirmation `TODO(human)` as `5.ULB Dispatch/app/closure.py`.

## Tests

```bash
pytest -q
```
Mocked-DB only, no live Postgres required.
