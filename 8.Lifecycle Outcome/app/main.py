from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.closure import verify_pilot
from app.config import settings
from app.db import Proposal, get_db
from app.storage import storage
from app.disposition import apply_disposition, record_patent
from app.milestones import evaluate_milestone, get_milestones, initialize_milestones, reconcile as reconcile_milestones
from app.schemas import DispositionRequest, LifecycleAck, MilestoneOut, PatentFilingRequest, PatentRecordOut, PilotValidationOut, ReconcileResult

logger = logging.getLogger("lifecycle_outcome")

app = FastAPI(title="Sahyog Lifecycle Outcome", version="0.1.0")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid X-Internal-Token")


@app.post("/lifecycle/reconcile", response_model=ReconcileResult, dependencies=[Depends(require_internal_token)])
def lifecycle_reconcile(db: Session = Depends(get_db)):
    # Registered before /lifecycle/proposal-approved/{proposal_id} - same
    # path-shadowing lesson as every other service in this repo.
    result = reconcile_milestones(db)
    return ReconcileResult(**result)


@app.post("/lifecycle/proposal-approved/{proposal_id}", response_model=LifecycleAck, dependencies=[Depends(require_internal_token)])
def lifecycle_entry(proposal_id: int, db: Session = Depends(get_db)):
    try:
        result = initialize_milestones(db, proposal_id)
    except Exception as exc:  # noqa: BLE001 - the webhook caller must never see an unhandled 500
        logger.exception("lifecycle_entry failed for proposal_id=%s", proposal_id)
        return JSONResponse(status_code=500, content={"proposal_id": proposal_id, "created": False, "detail": str(exc)})
    return LifecycleAck(**result)


# ---------------------------------------------------------------------------
# Admin Portal proxy targets (4.Orchestrator calls these server-side - see
# 6.Track B Innovation/app/main.py's equivalent section for the full
# rationale on internal-auth vs HTTPBasic here).
#
# GET /lifecycle/pending-dispositions is registered BEFORE
# GET /lifecycle/{ticket_id} - Starlette matches routes in registration
# order, and {ticket_id} would otherwise greedily match the literal path
# segment "pending-dispositions" first (as a to-be-rejected int) and shadow
# this route entirely - same class of bug as 5.ULB Dispatch's
# /dispatch/reconcile vs /dispatch/{ticket_id} lesson, caught live this
# time by an actual Admin Portal click producing a 422 int-parsing error.
# ---------------------------------------------------------------------------

@app.get("/lifecycle/pending-dispositions", dependencies=[Depends(require_internal_token)])
def pending_dispositions(db: Session = Depends(get_db)):
    """Tickets with a 'pass' pilot validation but no disposition recorded
    yet - the Admin Portal's actionable Lifecycle queue."""
    rows = db.execute(
        text(
            """
            SELECT pv.ticket_id, pv.proposal_id, pv.verdict, pv.created_at
            FROM pilot_validations pv
            WHERE pv.verdict = 'pass'
              AND pv.ticket_id NOT IN (SELECT ticket_id FROM handover_records)
              AND pv.proposal_id NOT IN (SELECT proposal_id FROM spinout_records)
            ORDER BY pv.created_at DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/lifecycle/{ticket_id}", response_model=list[MilestoneOut], dependencies=[Depends(require_internal_token)])
def get_lifecycle_status(ticket_id: int, db: Session = Depends(get_db)):
    proposal = db.query(Proposal).filter(Proposal.ticket_id == ticket_id).one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"no proposal found for ticket {ticket_id}")
    milestones = get_milestones(db, proposal.id)
    return [MilestoneOut.model_validate(m) for m in milestones]


@app.post("/lifecycle/{ticket_id}/disposition", dependencies=[Depends(require_internal_token)])
def lifecycle_disposition_json(ticket_id: int, body: DispositionRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /admin/{ticket_id}/disposition
    - same apply_disposition() call as the HTTPBasic form, so the two entry
    points can never drift out of sync."""
    try:
        result = apply_disposition(db, ticket_id, body.proposal_id, body.disposition, body.notes, body.startup_name, body.incubator_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.post("/lifecycle/{ticket_id}/patent", response_model=PatentRecordOut, dependencies=[Depends(require_internal_token)])
def lifecycle_patent_json(ticket_id: int, body: PatentFilingRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /admin/{ticket_id}/patent
    - same record_patent() call as the HTTPBasic form, so the two entry
    points can never drift out of sync."""
    try:
        record = record_patent(
            db, ticket_id, body.proposal_id, body.title, body.applicant_names,
            body.filing_status, body.application_number, body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PatentRecordOut.model_validate(record)


# ---------------------------------------------------------------------------
# Admin: milestone evaluation, pilot validation, disposition - human-
# operator actions, HTTPBasic via ADMIN_FORM_PASSWORD (separate trust
# boundary from INTERNAL_SERVICE_TOKEN, same separation as every other
# service in this repo).
# ---------------------------------------------------------------------------

_basic_auth = HTTPBasic(auto_error=False)


def require_admin_password(credentials: Optional[HTTPBasicCredentials] = Depends(_basic_auth)) -> None:
    if not settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_FORM_PASSWORD is not configured")
    if credentials is None or credentials.password != settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid admin credentials", headers={"WWW-Authenticate": "Basic"})


@app.post("/admin/milestones/{milestone_id}/evaluate", response_model=MilestoneOut, dependencies=[Depends(require_admin_password)])
def admin_evaluate_milestone(
    milestone_id: int, evaluator_name: str = Form(...), score: float = Form(...),
    notes: Optional[str] = Form(default=None), db: Session = Depends(get_db),
):
    try:
        milestone = evaluate_milestone(db, milestone_id, evaluator_name, score, notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MilestoneOut.model_validate(milestone)


_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _validate_photo_bytes(raw: bytes) -> None:
    if len(raw) > settings.MAX_PILOT_PHOTO_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"photo exceeds {settings.MAX_PILOT_PHOTO_MB}MB limit")
    if not (raw.startswith(_JPEG_MAGIC) or raw.startswith(_PNG_MAGIC)):
        raise HTTPException(status_code=400, detail="photo must be a JPEG or PNG (checked by file signature, not content-type header)")


@app.post("/admin/{ticket_id}/pilot-validate", response_model=PilotValidationOut, dependencies=[Depends(require_admin_password)])
async def admin_pilot_validate(
    ticket_id: int, proposal_id: int = Form(...), photo: Optional[UploadFile] = File(default=None),
    photo_lat: Optional[float] = Form(default=None), photo_lon: Optional[float] = Form(default=None),
    db: Session = Depends(get_db),
):
    if photo is None:
        raise HTTPException(status_code=400, detail="a photo is required for pilot validation")
    raw = await photo.read()
    _validate_photo_bytes(raw)

    content_type = "image/jpeg" if raw.startswith(_JPEG_MAGIC) else "image/png"
    object_key = storage.build_object_key("pilot-validations", photo.filename, default_ext=".jpg")
    uploaded = storage.upload(
        raw,
        media_type="image",
        content_type=content_type,
        object_key=object_key,
        original_filename=photo.filename,
        capture_lat=photo_lat,
        capture_lon=photo_lon,
    )

    try:
        validation = verify_pilot(
            db, ticket_id, proposal_id, raw, uploaded.url, uploaded.media_id, photo_lat, photo_lon,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return PilotValidationOut.model_validate(validation)


@app.post("/admin/{ticket_id}/disposition", dependencies=[Depends(require_admin_password)])
def admin_disposition(
    ticket_id: int, proposal_id: int = Form(...), disposition: str = Form(...),
    notes: Optional[str] = Form(default=None), startup_name: Optional[str] = Form(default=None),
    incubator_name: Optional[str] = Form(default=None), db: Session = Depends(get_db),
):
    try:
        result = apply_disposition(db, ticket_id, proposal_id, disposition, notes, startup_name, incubator_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.post("/admin/{ticket_id}/patent", response_model=PatentRecordOut, dependencies=[Depends(require_admin_password)])
def admin_patent(
    ticket_id: int, proposal_id: int = Form(...), title: str = Form(...),
    applicant_names: str = Form(default=""), filing_status: str = Form(default="filed"),
    application_number: Optional[str] = Form(default=None), notes: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    names = [n.strip() for n in applicant_names.split(",") if n.strip()]
    try:
        record = record_patent(db, ticket_id, proposal_id, title, names, filing_status, application_number, notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PatentRecordOut.model_validate(record)
