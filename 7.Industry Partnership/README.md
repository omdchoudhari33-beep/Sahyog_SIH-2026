# 7. Industry Partnership

Implements subgraph I from the SAHYOG architecture (I1 Partner Registry, I2 Mentor &
Sponsor Matching, I3 Tiered IP Ownership Template, I4 Milestone Fund Ledger, I5 NEP
Academic Credit & CSR Certificate). Runs on **port 8007**.

```
6.Track B Innovation (nodal officer approves a proposal)
    -> POST /partnership/proposal-approved/{proposal_id}  (this service, fire-and-forget webhook)
        -> I2 matches the proposal's domain against partner_capabilities
        -> partner notified; decline -> next-best partner (same re-route idiom as Track B)
        -> accept -> human ops records I3 IP tier, I4 opens/releases a milestone
           fund ledger, I5 issues NEP credit / CSR certificates
```

## Setup

1. Same Postgres instance/DB as the other services.
2. `psql "$DATABASE_URL" -f schema.sql` (additive-only, not auto-run at startup).
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`. `INTERNAL_SERVICE_TOKEN` must be the exact same
   value already used repo-wide (see `5.ULB Dispatch/README.md` / `6.Track B
   Innovation/README.md`).
5. `uvicorn app.main:app --port 8007`

With defaults (`SEED_DEMO_DATA=true`, `EMAIL_DRY_RUN=true`) one demo partner +
capability auto-seed on startup.

## Manual cross-service setup

`6.Track B Innovation/app/teams.py`'s `nodal_decide()` fires a non-blocking webhook
here on proposal approval, reusing the same shared `INTERNAL_SERVICE_TOKEN`. Set
`INDUSTRY_PARTNERSHIP_BASE_URL` in that service's `.env` if this one runs on a
different host/port than `http://localhost:8007`.

## Reconciliation safety net

`POST /partnership/reconcile` scans `proposals` (read cross-service, same DB) for
`status='approved'` rows with no `partnership_matches` row at all, and matches each
one. **Verified live**: on first startup it correctly picked up a proposal approved
before this service existed at all.

## Matching (I2)

Domain-keyword based, not semantic/embedding like Track B's HEI matcher - a proposal
doesn't carry a domain column directly, so this reads it off the originating ticket
via a read-only `active_tickets` mirror (same "each service reads only what it needs
from another service's table" idiom as everywhere else in this repo), then matches
against `partner_capabilities.domain` (or a capability tagged `'ANY'` as a catch-all).

## I3-I5: what's real and what's `TODO(human)`

None of these move real money, sign real documents, or issue real academic credit -
they record that a decision/commitment/issuance happened, by whom, with real
validation (e.g. a fund release can never exceed the committed amount - enforced and
tested), giving a genuine audit trail to build a real integration against later:

- **I3 IP agreements** (`/admin/ip-agreement`): records a tier
  (hei_owned/shared/partner_owned/open_source). `# TODO(human)`: actual legal
  template content and any e-signature integration.
- **I4 Milestone Fund Ledger** (`/admin/ledger/open`, `/admin/ledger/{id}/release`):
  tracks committed/released **amounts only**. `escrow_provider` is a label - `#
  TODO(human)`: real escrow/PFMS bank API integration (the architecture diagram
  itself marks this "future").
- **I5 NEP credits** (`/admin/nep-credit`): records that a credit/certificate was
  issued. `# TODO(human)`: real NEP academic-system integration and real certificate
  generation/signing.

All four `/admin/*` financial/legal actions are `HTTPBasic`-protected via
`ADMIN_FORM_PASSWORD` (human-operator actions, not automated service calls - a
different trust boundary from `INTERNAL_SERVICE_TOKEN`).

## Endpoints

**Internal only** (`X-Internal-Token`, `401` if missing/wrong):
`POST /partnership/reconcile`, `POST /partnership/proposal-approved/{proposal_id}`,
`GET /partnership/{proposal_id}`.

**Public** (token is the credential):
`GET /partner/{token}` / `POST /partner/{token}/decide`.

**Admin** (`HTTPBasic` via `ADMIN_FORM_PASSWORD`):
`GET/POST /admin/onboard-partner`, `POST /admin/ip-agreement`,
`POST /admin/ledger/open`, `POST /admin/ledger/{id}/release`,
`POST /admin/nep-credit`.

## Known limitations

- No cross-service FK constraints to `6.Track B Innovation`'s `proposals` table or
  `8.Lifecycle Outcome`'s `milestones` table - documented as a deliberate choice in
  `schema.sql` (each service's migration is applied independently; a hard FK would
  create a build-order dependency between services).
- Trust-on-registration for partner onboarding, same hackathon shortcut already
  flagged in `5.ULB Dispatch` and `6.Track B Innovation`.

## Tests

```bash
pytest -q
```
Mocked-DB only, no live Postgres required.
