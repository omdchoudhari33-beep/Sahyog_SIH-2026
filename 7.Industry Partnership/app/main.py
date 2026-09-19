from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import Depends, FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import MilestoneFundLedger, PartnershipMatch, SessionLocal, get_db
from app.funding import issue_nep_credit, open_ledger, record_ip_agreement, release_funds
from app.onboarding import onboard_partner
from app.partnership import create_match, decide_match, reconcile as reconcile_matches
from app.schemas import FundReleaseRequest, LedgerOut, PartnershipAck, PartnershipMatchOut, ReconcileResult

logger = logging.getLogger("industry_partnership")


def _seed_demo_data_if_empty() -> None:
    db = SessionLocal()
    try:
        count = db.execute(text("SELECT COUNT(*) FROM partners")).scalar_one()
        if count > 0:
            return
        partner_id = db.execute(
            text(
                "INSERT INTO partners (name, type, contact_email, active) "
                "VALUES (:name, 'industry', :email, true) RETURNING id"
            ),
            {"name": settings.DEMO_PARTNER_NAME, "email": settings.DEMO_PARTNER_CONTACT_EMAIL},
        ).scalar_one()
        db.execute(
            text("INSERT INTO partner_capabilities (partner_id, domain, offering_type, active) VALUES (:partner_id, 'ROADS_BRIDGES', 'both', true)"),
            {"partner_id": partner_id},
        )
        db.commit()
        logger.info("[demo-seed] inserted demo partner (partner_id=%s) - set SEED_DEMO_DATA=false to disable", partner_id)
    finally:
        db.close()


app = FastAPI(title="Sahyog Industry Partnership", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    if settings.SEED_DEMO_DATA:
        _seed_demo_data_if_empty()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid X-Internal-Token")


@app.post("/partnership/reconcile", response_model=ReconcileResult, dependencies=[Depends(require_internal_token)])
def partnership_reconcile(db: Session = Depends(get_db)):
    # Registered before /partnership/proposal-approved/{proposal_id} - same
    # path-shadowing lesson as every other service in this repo.
    result = reconcile_matches(db)
    return ReconcileResult(**result)


@app.post("/partnership/proposal-approved/{proposal_id}", response_model=PartnershipAck, dependencies=[Depends(require_internal_token)])
def partnership_entry(proposal_id: int, db: Session = Depends(get_db)):
    try:
        result = create_match(db, proposal_id)
    except Exception as exc:  # noqa: BLE001 - the webhook caller must never see an unhandled 500
        logger.exception("partnership_entry failed for proposal_id=%s", proposal_id)
        return JSONResponse(status_code=500, content={"proposal_id": proposal_id, "created": False, "detail": str(exc)})

    match = result.get("match")
    return PartnershipAck(
        proposal_id=proposal_id,
        match=PartnershipMatchOut.model_validate(match) if match is not None and match.id is not None else None,
        created=bool(result.get("created")),
        detail=result.get("detail"),
    )


# ---------------------------------------------------------------------------
# Admin Portal proxy targets (4.Orchestrator calls these server-side - see
# 6.Track B Innovation/app/main.py's equivalent section for the full
# rationale on internal-auth vs HTTPBasic here).
#
# Registered BEFORE GET /partnership/{proposal_id} - Starlette matches
# routes in registration order, and {proposal_id} would otherwise greedily
# match the literal path segment "ledgers" first (as a to-be-rejected int)
# and shadow this route entirely - same class of bug as 5.ULB Dispatch's
# /dispatch/reconcile vs /dispatch/{ticket_id} lesson, caught live this
# time by an actual Admin Portal click producing a 422 int-parsing error.
# ---------------------------------------------------------------------------

@app.get("/partnership/ledgers", response_model=list[LedgerOut], dependencies=[Depends(require_internal_token)])
def list_ledgers(db: Session = Depends(get_db)):
    ledgers = db.query(MilestoneFundLedger).order_by(MilestoneFundLedger.created_at.desc()).all()
    return [LedgerOut.model_validate(l) for l in ledgers]


@app.post("/partnership/ledgers/{ledger_id}/release", dependencies=[Depends(require_internal_token)])
def release_ledger_funds_json(ledger_id: int, body: FundReleaseRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /admin/ledger/{id}/release
    - same release_funds() call as the HTTPBasic form, so the two entry
    points can never drift out of sync."""
    try:
        release = release_funds(db, ledger_id, body.amount, body.released_by, body.milestone_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"release_id": release.id, "amount_released": str(release.amount_released)}


@app.get("/partnership/{proposal_id}", response_model=PartnershipMatchOut, dependencies=[Depends(require_internal_token)])
def get_partnership_match(proposal_id: int, db: Session = Depends(get_db)):
    match = db.query(PartnershipMatch).filter(PartnershipMatch.proposal_id == proposal_id).order_by(PartnershipMatch.created_at.desc()).first()
    if match is None:
        raise HTTPException(status_code=404, detail=f"no match found for proposal {proposal_id}")
    return PartnershipMatchOut.model_validate(match)


# ---------------------------------------------------------------------------
# Public partner accept/decline - token is the credential.
# ---------------------------------------------------------------------------

def _partner_page_html(token: str, match: PartnershipMatch) -> str:
    if match.status == "proposed":
        body = f"""
        <p>You have a proposed {match.match_type} match.</p>
        <form method="post" action="/partner/{token}/decide">
          <button name="decision" value="accept" type="submit">Accept</button>
          <button name="decision" value="decline" type="submit">Decline</button>
        </form>
        """
    else:
        body = f"<p>This match was {match.status}.</p>"
    return f"""
    <!DOCTYPE html>
    <html><head><title>SAHYOG Industry Partnership</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body {{ font-family: sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; }}
    button {{ display:block; width:100%; padding:12px; margin:8px 0; font-size:16px; }}</style></head>
    <body><h2>SAHYOG Industry Partnership</h2>{body}</body></html>
    """


@app.get("/partner/{token}", response_class=HTMLResponse)
def partner_page(token: str, db: Session = Depends(get_db)):
    match = db.query(PartnershipMatch).filter(PartnershipMatch.match_token == token).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="match token not found")
    return HTMLResponse(_partner_page_html(token, match))


@app.post("/partner/{token}/decide")
def partner_decide(token: str, decision: str = Form(...), db: Session = Depends(get_db)):
    if decision not in ("accept", "decline"):
        raise HTTPException(status_code=400, detail="decision must be accept or decline")
    try:
        result = decide_match(db, token, decision)
    except LookupError:
        raise HTTPException(status_code=404, detail="match token not found")
    except TimeoutError:
        raise HTTPException(status_code=410, detail="match token has expired")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": result["match"].status, "re_routed": result.get("re_routed", False)}


# ---------------------------------------------------------------------------
# Admin: onboarding, IP agreements, milestone fund ledger, NEP credits -
# HTTPBasic, separate trust boundary from INTERNAL_SERVICE_TOKEN.
# ---------------------------------------------------------------------------

_basic_auth = HTTPBasic(auto_error=False)


def require_admin_password(credentials: Optional[HTTPBasicCredentials] = Depends(_basic_auth)) -> None:
    if not settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_FORM_PASSWORD is not configured")
    if credentials is None or credentials.password != settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid admin credentials", headers={"WWW-Authenticate": "Basic"})


@app.get("/admin/onboard-partner", response_class=HTMLResponse, dependencies=[Depends(require_admin_password)])
def onboard_partner_form():
    return HTMLResponse("""
    <!DOCTYPE html><html><head><title>Onboard Partner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px}
    label{display:block;margin-top:12px}input,select{width:100%;padding:8px}button{margin-top:16px;padding:10px 16px}</style>
    </head><body><h2>Onboard a Partner</h2>
    <form method="post" action="/admin/onboard-partner">
      <label>Name <input name="name" required></label>
      <label>Type <select name="type"><option>industry</option><option>msme</option><option>startup</option><option>csr</option><option>lab</option></select></label>
      <label>Sector <input name="sector"></label>
      <label>Contact name <input name="contact_name"></label>
      <label>Contact email <input name="contact_email" type="email" required></label>
      <label>Contact phone <input name="contact_phone"></label>
      <label>Domain (e.g. ROADS_BRIDGES) <input name="domain" required></label>
      <label>Offering type <select name="offering_type"><option>mentorship</option><option>sponsorship</option><option>both</option></select></label>
      <button type="submit">Add partner</button>
    </form></body></html>
    """)


@app.post("/admin/onboard-partner", dependencies=[Depends(require_admin_password)])
def onboard_partner_submit(
    name: str = Form(...), type: str = Form(...), sector: Optional[str] = Form(default=None),
    contact_name: Optional[str] = Form(default=None), contact_email: str = Form(...),
    contact_phone: Optional[str] = Form(default=None), domain: str = Form(...),
    offering_type: str = Form(default="mentorship"), db: Session = Depends(get_db),
):
    try:
        partner, capability = onboard_partner(db, name, type, sector, contact_name, contact_email, contact_phone, domain, offering_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"partner_id": partner.id, "capability_id": capability.id}


@app.post("/admin/ip-agreement", dependencies=[Depends(require_admin_password)])
def admin_record_ip_agreement(
    proposal_id: int = Form(...), partner_id: Optional[int] = Form(default=None),
    tier: str = Form(...), document_url: Optional[str] = Form(default=None), db: Session = Depends(get_db),
):
    try:
        agreement = record_ip_agreement(db, proposal_id, partner_id, tier, document_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"agreement_id": agreement.id, "tier": agreement.tier}


@app.post("/admin/ledger/open", dependencies=[Depends(require_admin_password)])
def admin_open_ledger(
    proposal_id: int = Form(...), partner_id: Optional[int] = Form(default=None),
    total_committed_amount: Decimal = Form(...), escrow_provider: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        ledger = open_ledger(db, proposal_id, partner_id, total_committed_amount, escrow_provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ledger_id": ledger.id, "status": ledger.status}


@app.post("/admin/ledger/{ledger_id}/release", dependencies=[Depends(require_admin_password)])
def admin_release_funds(
    ledger_id: int, amount: Decimal = Form(...), released_by: str = Form(...),
    milestone_id: Optional[int] = Form(default=None), db: Session = Depends(get_db),
):
    try:
        release = release_funds(db, ledger_id, amount, released_by, milestone_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"release_id": release.id, "amount_released": str(release.amount_released)}


@app.post("/admin/nep-credit", dependencies=[Depends(require_admin_password)])
def admin_issue_nep_credit(
    proposal_id: int = Form(...), team_member_name: str = Form(...), credit_type: str = Form(...),
    credits_awarded: Optional[Decimal] = Form(default=None), certificate_url: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        credit = issue_nep_credit(db, proposal_id, team_member_name, credit_type, credits_awarded, certificate_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"credit_id": credit.id, "credit_type": credit.credit_type}
