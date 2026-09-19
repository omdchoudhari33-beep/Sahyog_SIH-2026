from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.closure import verify_closure
from app.config import settings
from app.db import Dispatch, DispatchEvent, SessionLocal, get_db
from app.storage import storage
from app.dispatch import create_dispatch, reconcile as reconcile_dispatches
from app.inbox_poller import poll_inbox
from app.onboarding import list_ulbs, onboard_contact
from app.schemas import (
    DispatchAck,
    DispatchDetail,
    DispatchEventOut,
    DispatchOut,
    OnboardResult,
    ReconcileResult,
)
from app.sla import scan_overdue
from app.status_links import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    mark_token_used,
    resolve_status_token,
)

logger = logging.getLogger("ulb_dispatch")

EMAIL_TEMPLATES_STATUS_PAGE = {
    "en": {
        "title": "SAHYOG - Update Ticket Status",
        "ack": "Acknowledge",
        "in_progress": "Mark In Progress",
        "resolved": "Mark Resolved (photo required)",
        "photo_label": "Upload after-photo",
        "submit": "Submit",
    }
}


# ---------------------------------------------------------------------------
# Startup: demo data seeding + in-process background loop (Step 2b)
# ---------------------------------------------------------------------------

def _seed_demo_data_if_empty() -> None:
    db = SessionLocal()
    try:
        count = db.execute(text("SELECT COUNT(*) FROM ulb_directory")).scalar_one()
        if count > 0:
            return
        ulb_id = db.execute(
            text(
                "INSERT INTO ulb_directory (name, state, district, boundary, active) "
                "VALUES (:name, :state, :district, ST_GeomFromText(:wkt, 4326), true) "
                "RETURNING id"
            ),
            {
                "name": "Demo ULB (auto-seeded)",
                "state": "TODO(human): set real state",
                "district": None,
                "wkt": settings.DEMO_ULB_BOUNDARY_WKT,
            },
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO ulb_contacts (ulb_id, domain, dept_name, level, channel, email, verified_at, active) "
                "VALUES (:ulb_id, NULL, 'Demo catch-all office', 1, 'email', :email, now(), true)"
            ),
            {"ulb_id": ulb_id, "email": settings.DEMO_CONTACT_EMAIL},
        )
        db.commit()
        logger.info(
            "[demo-seed] inserted demo ULB + contact (ulb_id=%s, email=%s) - "
            "set SEED_DEMO_DATA=false to disable",
            ulb_id, settings.DEMO_CONTACT_EMAIL,
        )
    finally:
        db.close()


async def _background_loop() -> None:
    """Runs sla.scan_overdue + inbox_poller.poll_inbox + dispatch.reconcile
    on their configured intervals, in-process. See worker.py for the
    separate-process equivalent (used when RUN_BACKGROUND_LOOP_IN_PROCESS=false)."""
    last_inbox_poll = 0.0
    loop = asyncio.get_event_loop()

    while True:
        db = SessionLocal()
        try:
            await asyncio.to_thread(scan_overdue, db)
            await asyncio.to_thread(reconcile_dispatches, db)
        except Exception:  # noqa: BLE001 - background loop must never die silently
            logger.exception("[background-loop] sla/reconcile pass failed")
        finally:
            db.close()

        now = loop.time()
        if now - last_inbox_poll >= settings.INBOX_POLL_INTERVAL_SECONDS:
            db = SessionLocal()
            try:
                await asyncio.to_thread(poll_inbox, db)
            except Exception:  # noqa: BLE001
                logger.exception("[background-loop] inbox poll failed")
            finally:
                db.close()
            last_inbox_poll = now

        await asyncio.sleep(settings.SLA_POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SEED_DEMO_DATA:
        _seed_demo_data_if_empty()

    task: Optional[asyncio.Task] = None
    if settings.RUN_BACKGROUND_LOOP_IN_PROCESS:
        logger.info("[background-loop] starting in-process (set RUN_BACKGROUND_LOOP_IN_PROCESS=false to disable and use worker.py instead)")
        task = asyncio.create_task(_background_loop())

    yield

    if task is not None:
        task.cancel()


app = FastAPI(title="Sahyog ULB Dispatch (Track A)", version="0.1.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def root():
    # This service has no citizen-facing homepage - it's an internal API
    # (see 3.Triage and route's fire-and-forget webhook) plus a couple of
    # public, credential-in-URL pages. Redirect here to /docs so hitting
    # the bare root in a browser is useful instead of a bare 404.
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Internal auth - required on all /dispatch/* routes, not on /status/* or the
# onboarding form (those have their own, separate credentials).
# ---------------------------------------------------------------------------

def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid X-Internal-Token")


@app.post("/dispatch/reconcile", response_model=ReconcileResult, dependencies=[Depends(require_internal_token)])
def dispatch_reconcile(db: Session = Depends(get_db)):
    # Must be registered BEFORE POST /dispatch/{ticket_id} - Starlette
    # matches routes in registration order, and {ticket_id} would otherwise
    # greedily match the literal path segment "reconcile" first (as a
    # to-be-rejected int) and shadow this route entirely.
    result = reconcile_dispatches(db)
    return ReconcileResult(**result)


@app.get("/dispatch", response_model=list[DispatchOut], dependencies=[Depends(require_internal_token)])
def list_dispatches(limit: int = 50, db: Session = Depends(get_db)):
    """List recent dispatches, newest first - for the Admin Portal's Track A
    overview (4.Orchestrator proxies this, the browser never calls it
    directly). Distinct path shape from /dispatch/{ticket_id} (no path
    param), so no route-ordering conflict with it."""
    dispatches = db.query(Dispatch).order_by(Dispatch.sent_at.desc()).limit(min(limit, 200)).all()
    return [DispatchOut.model_validate(d) for d in dispatches]


@app.post("/dispatch/{ticket_id}", response_model=DispatchAck, dependencies=[Depends(require_internal_token)])
def dispatch_ticket(ticket_id: int, db: Session = Depends(get_db)):
    try:
        result = create_dispatch(db, ticket_id)
    except Exception as exc:  # noqa: BLE001 - Step 6's caller must never see an unhandled 500 body-less error
        logger.exception("dispatch_ticket failed for ticket_id=%s", ticket_id)
        return JSONResponse(status_code=500, content={"ticket_id": ticket_id, "created": False, "detail": str(exc)})

    dispatch = result.get("dispatch")
    return DispatchAck(
        ticket_id=ticket_id,
        dispatch=DispatchOut.model_validate(dispatch) if dispatch is not None and dispatch.id is not None else None,
        created=bool(result.get("created")),
        detail=result.get("detail"),
    )


@app.get("/dispatch/{ticket_id}", response_model=DispatchDetail, dependencies=[Depends(require_internal_token)])
def get_dispatch(ticket_id: int, db: Session = Depends(get_db)):
    dispatch = (
        db.query(Dispatch)
        .filter(Dispatch.ticket_id == ticket_id)
        .order_by(Dispatch.sent_at.desc())
        .first()
    )
    if dispatch is None:
        raise HTTPException(status_code=404, detail=f"no dispatch found for ticket {ticket_id}")
    events = db.query(DispatchEvent).filter(DispatchEvent.dispatch_id == dispatch.id).order_by(DispatchEvent.occurred_at.asc()).all()
    return DispatchDetail(
        dispatch=DispatchOut.model_validate(dispatch),
        events=[DispatchEventOut.model_validate(e) for e in events],
    )


# ---------------------------------------------------------------------------
# Public status link routes - the token itself is the credential.
# ---------------------------------------------------------------------------

def _status_page_html(token: str, message: str = "") -> str:
    tpl = EMAIL_TEMPLATES_STATUS_PAGE["en"]
    return f"""
    <!DOCTYPE html>
    <html><head><title>{tpl['title']}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body {{ font-family: sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; }}
      button {{ display:block; width:100%; padding:12px; margin:8px 0; font-size:16px; }}
      .msg {{ color: #a00; margin-bottom: 12px; }}
    </style></head>
    <body>
      <h2>{tpl['title']}</h2>
      {f'<p class="msg">{message}</p>' if message else ''}
      <form method="post" action="/status/{token}/update" enctype="multipart/form-data">
        <button name="status" value="acked" type="submit">{tpl['ack']}</button>
        <button name="status" value="in_progress" type="submit">{tpl['in_progress']}</button>
        <p>{tpl['photo_label']}: <input type="file" name="photo" accept="image/jpeg,image/png"></p>
        <button name="status" value="resolved" type="submit">{tpl['resolved']}</button>
      </form>
    </body></html>
    """


@app.get("/status/{token}", response_class=HTMLResponse)
def status_page(token: str, db: Session = Depends(get_db)):
    try:
        resolve_status_token(db, token)
    except LookupError:
        raise HTTPException(status_code=404, detail="status link not found")
    except TokenExpiredError:
        raise HTTPException(status_code=410, detail="status link has expired")
    except TokenAlreadyUsedError:
        raise HTTPException(status_code=410, detail="status link has already been used")
    return HTMLResponse(_status_page_html(token))


_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _validate_photo_bytes(raw: bytes) -> None:
    if len(raw) > settings.MAX_CLOSURE_PHOTO_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"photo exceeds {settings.MAX_CLOSURE_PHOTO_MB}MB limit")
    if not (raw.startswith(_JPEG_MAGIC) or raw.startswith(_PNG_MAGIC)):
        raise HTTPException(status_code=400, detail="photo must be a JPEG or PNG (checked by file signature, not content-type header)")


@app.post("/status/{token}/update")
async def status_update(
    token: str,
    status: str = Form(...),
    photo: Optional[UploadFile] = None,
    photo_lat: Optional[float] = Form(default=None),
    photo_lon: Optional[float] = Form(default=None),
    db: Session = Depends(get_db),
):
    if status not in ("acked", "in_progress", "resolved"):
        raise HTTPException(status_code=400, detail="status must be one of acked, in_progress, resolved")

    try:
        token_row = resolve_status_token(db, token)
    except LookupError:
        raise HTTPException(status_code=404, detail="status link not found")
    except TokenExpiredError:
        raise HTTPException(status_code=410, detail="status link has expired")
    except TokenAlreadyUsedError:
        raise HTTPException(status_code=410, detail="status link has already been used")

    dispatch = db.query(Dispatch).filter(Dispatch.id == token_row.dispatch_id).one_or_none()
    if dispatch is None:
        raise HTTPException(status_code=404, detail="dispatch not found for this status link")

    if status == "resolved":
        if photo is None:
            raise HTTPException(status_code=400, detail="a photo is required to mark resolved")
        raw = await photo.read()
        _validate_photo_bytes(raw)

        content_type = "image/jpeg" if raw.startswith(_JPEG_MAGIC) else "image/png"
        object_key = storage.build_object_key("closure-proofs", photo.filename, default_ext=".jpg")
        uploaded = storage.upload(
            raw,
            media_type="image",
            content_type=content_type,
            object_key=object_key,
            original_filename=photo.filename,
            capture_lat=photo_lat,
            capture_lon=photo_lon,
        )

        proof = verify_closure(
            db,
            dispatch_id=dispatch.id,
            photo_bytes=raw,
            photo_url=uploaded.url,
            photo_media_id=uploaded.media_id,
            photo_lat=photo_lat,
            photo_lon=photo_lon,
            exif_captured_at=None,
            submitted_by="officer",
        )
        mark_token_used(db, token_row)
        db.commit()
        return {"status": "resolved", "closure_proof_id": proof.id, "verified": proof.verified_at is not None}

    dispatch.status = status
    db.add(dispatch)
    db.add(DispatchEvent(dispatch_id=dispatch.id, event_type=status if status == "acked" else "acked", source="status_link", payload={"status": status}))
    mark_token_used(db, token_row)
    db.commit()
    return {"status": status}


# ---------------------------------------------------------------------------
# Admin onboarding form - protected by ADMIN_FORM_PASSWORD (a separate trust
# boundary from INTERNAL_SERVICE_TOKEN).
# ---------------------------------------------------------------------------

_basic_auth = HTTPBasic(auto_error=False)


def require_admin_password(credentials: Optional[HTTPBasicCredentials] = Depends(_basic_auth)) -> None:
    if not settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_FORM_PASSWORD is not configured")
    if credentials is None or credentials.password != settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid admin credentials", headers={"WWW-Authenticate": "Basic"})


def _onboard_form_html(ulbs, known_domains: list[str]) -> str:
    options = "".join(f'<option value="{u.id}">{u.name}</option>' for u in ulbs)
    datalist = "".join(f'<option value="{d}">' for d in known_domains)
    return f"""
    <!DOCTYPE html>
    <html><head><title>Onboard a ULB contact</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body {{ font-family: sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; }}
    label {{ display:block; margin-top:12px; }} input, select {{ width:100%; padding:8px; }}
    button {{ margin-top:16px; padding:10px 16px; }}</style></head>
    <body>
      <h2>Onboard a ULB contact</h2>
      <p style="color:#a00">Note: submitting this form marks the contact as
      verified immediately (trust-on-registration). This is a hackathon
      shortcut, not a production security control.</p>
      <form method="post" action="/admin/onboard">
        <label>ULB <select name="ulb_id">{options}</select></label>
        <label>Domain (optional, e.g. ROADS_BRIDGES) <input list="domains" name="domain">
          <datalist id="domains">{datalist}</datalist>
        </label>
        <label>Department name <input name="dept_name" required></label>
        <label>Officer name <input name="officer_name"></label>
        <label>Officer phone <input name="officer_phone"></label>
        <label>Email <input name="email" type="email" required></label>
        <label>Channel
          <select name="channel"><option value="email" selected>email</option><option value="api">api</option></select>
        </label>
        <button type="submit">Add contact</button>
      </form>
    </body></html>
    """


_KNOWN_TRACK_A_DOMAINS = [
    "ROADS_BRIDGES", "WASTE_GARBAGE_COLLECTION", "WATER_SUPPLY", "SANITATION_SEWAGE",
    "STREETLIGHTING", "DRAINAGE_WATERLOGGING", "PARKS_PUBLIC_SPACES", "TRAFFIC_SIGNAGE",
    "ENERGY_POWER", "STRAY_ANIMAL_MANAGEMENT", "HEALTHCARE_FACILITY_MAINTENANCE",
    "EDUCATION_FACILITY_MAINTENANCE", "CIVIC_DISASTER_EMERGENCY",
]


@app.get("/admin/onboard", response_class=HTMLResponse, dependencies=[Depends(require_admin_password)])
def onboard_form(db: Session = Depends(get_db)):
    ulbs = list_ulbs(db)
    return HTMLResponse(_onboard_form_html(ulbs, _KNOWN_TRACK_A_DOMAINS))


@app.post("/admin/onboard", response_model=OnboardResult, dependencies=[Depends(require_admin_password)])
def onboard_submit(
    ulb_id: int = Form(...),
    domain: Optional[str] = Form(default=None),
    dept_name: str = Form(...),
    officer_name: Optional[str] = Form(default=None),
    officer_phone: Optional[str] = Form(default=None),
    email: str = Form(...),
    channel: str = Form(default="email"),
    db: Session = Depends(get_db),
):
    try:
        contact = onboard_contact(
            db, ulb_id=ulb_id, domain=domain, dept_name=dept_name,
            officer_name=officer_name, officer_phone=officer_phone, email=email, channel=channel,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OnboardResult(contact_id=contact.id, ulb_id=contact.ulb_id, domain=contact.domain, dept_name=contact.dept_name, channel=contact.channel)
