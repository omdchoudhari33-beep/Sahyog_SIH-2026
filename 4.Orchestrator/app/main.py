import time
import uuid
from pathlib import Path
from typing import Literal, Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.clients import (
    _client as agent_client,
    apply_lifecycle_disposition,
    call_agent1,
    call_agent1_speak,
    call_agent2,
    call_agent2_attach_photo,
    call_agent3_ingest,
    decide_nodal_proposal,
    get_transparency_dashboard,
    list_agent3_tickets,
    list_fund_ledgers,
    list_pending_dispositions,
    list_pending_proposals,
    list_track_a_dispatches,
    release_ledger_funds,
    submit_agent3_decision,
    upload_audio_to_agent1,
)
from app.config import settings
from app.conversation import create_session, get_session
from app.geocoding import geocode_address
from app.mapping import build_ticket_payload
from app.schemas import PipelineResult

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title=settings.app_name)


@app.on_event("shutdown")
async def close_agent_client():
    await agent_client.aclose()


class _Stage:
    """Times one pipeline stage and prints it, so a slow turn can be
    attributed to a specific ASR/LLM/translate/TTS call instead of guessed
    at - each of those is a real model-inference hop, not a cheap request."""

    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        elapsed = time.perf_counter() - self._start
        print(f"[timing] {self.label}: {elapsed:.2f}s")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def serve_citizen_form():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------------
# Admin auth - gates the DNO dashboard AND the unified Admin Portal below.
# Separate credential from any per-service secret (HTTPBasic against
# admin_portal_password), same trust-boundary pattern every other service
# in this repo uses for its own /admin/* routes.
# ---------------------------------------------------------------------------

_basic_auth = HTTPBasic(auto_error=False)


def require_admin_portal_password(credentials: Optional[HTTPBasicCredentials] = Depends(_basic_auth)) -> None:
    if not settings.admin_portal_password:
        raise HTTPException(status_code=503, detail="admin_portal_password is not configured")
    if credentials is None or credentials.password != settings.admin_portal_password:
        raise HTTPException(status_code=401, detail="invalid admin credentials", headers={"WWW-Authenticate": "Basic"})


@app.get("/dashboard", dependencies=[Depends(require_admin_portal_password)])
def serve_operator_dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html")


class DecisionPayload(BaseModel):
    decision: Literal["track_a", "track_b", "reject_merge"]
    operator_id: Optional[str] = None
    notes: Optional[str] = None


@app.get("/api/tickets", dependencies=[Depends(require_admin_portal_password)])
async def api_list_tickets(limit: int = 50, offset: int = 0):
    """Dashboard proxy: keeps Agent 3 off the public network, browser only talks to us."""
    try:
        return await list_agent3_tickets(limit, offset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent 3 unavailable: {exc}") from exc


class SpeakPayload(BaseModel):
    text: str
    language: Optional[str] = "en"


@app.post("/speak")
async def api_speak(payload: SpeakPayload):
    """Proxy for Agent 1's TTS - browser never talks to Agent 1 directly.
    Returns 204 (no body) if speech isn't available; the citizen still has
    the text on screen either way."""
    try:
        with _Stage("agent1 speak (Bhashini translate + TTS)"):
            audio_bytes = await call_agent1_speak(payload.text, payload.language)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent 1 unavailable: {exc}") from exc

    if audio_bytes is None:
        return Response(status_code=204)
    return Response(content=audio_bytes, media_type="audio/wav")


@app.post("/api/tickets/{ticket_id}/decision", dependencies=[Depends(require_admin_portal_password)])
async def api_submit_decision(ticket_id: int, payload: DecisionPayload):
    try:
        return await submit_agent3_decision(
            ticket_id, payload.decision, payload.operator_id, payload.notes
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.text
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent 3 unavailable: {exc}") from exc


# ---------------------------------------------------------------------------
# Unified Admin Portal - one login, one URL, proxying into services 5-9's
# admin actions. The browser only ever talks to THIS service (same
# "proxied through the orchestrator" rule the DNO queue above already
# follows for Agent 3); each downstream call below carries
# X-Internal-Token, added by the client functions in app/clients.py.
# ---------------------------------------------------------------------------

@app.get("/admin", dependencies=[Depends(require_admin_portal_password)])
def serve_admin_portal():
    return FileResponse(STATIC_DIR / "admin.html")


def _proxy_error(service: str, exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.HTTPStatusError):
        return HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    return HTTPException(status_code=502, detail=f"{service} unavailable: {exc}")


@app.get("/api/admin/track-a", dependencies=[Depends(require_admin_portal_password)])
async def admin_track_a(limit: int = 50):
    try:
        return await list_track_a_dispatches(limit)
    except Exception as exc:
        raise _proxy_error("5.ULB Dispatch", exc) from exc


@app.get("/api/admin/track-b/pending", dependencies=[Depends(require_admin_portal_password)])
async def admin_track_b_pending():
    try:
        return await list_pending_proposals()
    except Exception as exc:
        raise _proxy_error("6.Track B Innovation", exc) from exc


class NodalDecisionPayload(BaseModel):
    decision: Literal["approved", "rejected", "revision_requested"]
    nodal_officer_id: str
    notes: Optional[str] = None


@app.post("/api/admin/track-b/{proposal_id}/decide", dependencies=[Depends(require_admin_portal_password)])
async def admin_track_b_decide(proposal_id: int, payload: NodalDecisionPayload):
    try:
        return await decide_nodal_proposal(proposal_id, payload.decision, payload.nodal_officer_id, payload.notes)
    except Exception as exc:
        raise _proxy_error("6.Track B Innovation", exc) from exc


@app.get("/api/admin/industry/ledgers", dependencies=[Depends(require_admin_portal_password)])
async def admin_industry_ledgers():
    try:
        return await list_fund_ledgers()
    except Exception as exc:
        raise _proxy_error("7.Industry Partnership", exc) from exc


class ReleaseFundsPayload(BaseModel):
    amount: str
    released_by: str
    milestone_id: Optional[int] = None


@app.post("/api/admin/industry/ledgers/{ledger_id}/release", dependencies=[Depends(require_admin_portal_password)])
async def admin_industry_release(ledger_id: int, payload: ReleaseFundsPayload):
    try:
        return await release_ledger_funds(ledger_id, payload.amount, payload.released_by, payload.milestone_id)
    except Exception as exc:
        raise _proxy_error("7.Industry Partnership", exc) from exc


@app.get("/api/admin/lifecycle/pending", dependencies=[Depends(require_admin_portal_password)])
async def admin_lifecycle_pending():
    try:
        return await list_pending_dispositions()
    except Exception as exc:
        raise _proxy_error("8.Lifecycle Outcome", exc) from exc


class DispositionPayload(BaseModel):
    proposal_id: int
    disposition: Literal["handover", "spinout", "both"]
    notes: Optional[str] = None
    startup_name: Optional[str] = None
    incubator_name: Optional[str] = None


@app.post("/api/admin/lifecycle/{ticket_id}/disposition", dependencies=[Depends(require_admin_portal_password)])
async def admin_lifecycle_disposition(ticket_id: int, payload: DispositionPayload):
    try:
        return await apply_lifecycle_disposition(
            ticket_id, payload.proposal_id, payload.disposition, payload.notes, payload.startup_name, payload.incubator_name
        )
    except Exception as exc:
        raise _proxy_error("8.Lifecycle Outcome", exc) from exc


@app.get("/api/admin/transparency", dependencies=[Depends(require_admin_portal_password)])
async def admin_transparency():
    try:
        return await get_transparency_dashboard()
    except Exception as exc:
        raise _proxy_error("9.Transparency Layer", exc) from exc


@app.post("/submit", response_model=PipelineResult)
async def submit_report(
    text: Optional[str] = Form(default=None),
    local_audio_path: Optional[str] = Form(default=None),
    audio: Optional[UploadFile] = File(default=None),
    source_language: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    device_lat: Optional[float] = Form(default=None),
    device_lon: Optional[float] = Form(default=None),
    device_timestamp: Optional[str] = Form(default=None),
):
    """
    Runs one citizen report end to end: S1 language normalization -> S2
    evidence extraction -> S3 dedup/priority/routing. Stops early and
    reports which stage needs a human (low ASR confidence, no usable
    location) instead of guessing.
    """
    if not text and not local_audio_path and not audio:
        raise HTTPException(
            status_code=422,
            detail="Provide 'text', a recorded/uploaded 'audio' file, or 'local_audio_path'",
        )

    request_id = str(uuid.uuid4())

    if audio and not local_audio_path:
        audio_bytes = await audio.read()
        try:
            local_audio_path = await upload_audio_to_agent1(audio_bytes, audio.filename)
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Agent 1 audio upload failed: {exc}"
            ) from exc

    input_type = "audio" if local_audio_path else "text"

    # --- S1: language normalization / ASR / translation ---
    try:
        agent1_result = await call_agent1(
            request_id,
            input_type,
            text=text,
            local_audio_path=local_audio_path,
            source_language=source_language,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 1 (language normalizer) failed: {exc}"
        ) from exc

    if agent1_result.get("status") == "review_required":
        return PipelineResult(
            request_id=request_id,
            status="review_required",
            stage="language_normalization",
            detail=(
                "ASR confidence was below threshold; a human must review "
                "the transcript before evidence extraction runs."
            ),
            agent1=agent1_result,
        )

    raw_text = (
        agent1_result.get("english_translation")
        or agent1_result.get("standardized_text")
        or text
    )
    if not raw_text:
        raise HTTPException(status_code=502, detail="Agent 1 returned no usable text")

    # --- S2: evidence extraction (text + geo + vision) ---
    image_bytes = await image.read() if image else None
    try:
        agent2_result = await call_agent2(
            request_id,
            raw_text,
            image_bytes=image_bytes,
            image_filename=image.filename if image else None,
            device_lat=device_lat,
            device_lon=device_lon,
            device_timestamp=device_timestamp,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 2 (evidence extractor) failed: {exc}"
        ) from exc

    geolocation = agent2_result.get("geolocation") or {}
    latitude, longitude = geolocation.get("latitude"), geolocation.get("longitude")
    if latitude is None or longitude is None:
        return PipelineResult(
            request_id=request_id,
            status="geo_required",
            stage="evidence_extraction",
            detail=(
                "No usable location (EXIF GPS missing and no device "
                "coordinates supplied); geospatial dedup needs it."
            ),
            agent1=agent1_result,
            agent2=agent2_result,
        )

    # --- S3: dedup + priority + routing suggestion ---
    ticket_payload = build_ticket_payload(
        agent2_result["structured_evidence"],
        latitude,
        longitude,
        agent2_result,
        settings.default_population_impact,
    )

    try:
        agent3_result = await call_agent3_ingest(ticket_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 3 (triage & route) failed: {exc}"
        ) from exc

    status = (
        "review_required" if agent2_result.get("requires_human_review") else "routed"
    )
    return PipelineResult(
        request_id=request_id,
        status=status,
        stage="triage_and_route",
        detail=(
            "Ticket created/merged in the active queue; awaiting DNO human "
            "validation before dispatch."
        ),
        agent1=agent1_result,
        agent2=agent2_result,
        agent3=agent3_result,
    )


# ============================================================================
# Conversational flow: describe -> confirm -> photo -> (location) -> finalize
#
# Unlike /submit (one-shot, all-or-nothing), this validates the citizen's
# report at each step and lets them correct it before a ticket is raised -
# "AI assisting, not deciding": the human confirms what the AI understood.
# ============================================================================


class ConfirmPayload(BaseModel):
    confirmed: bool
    corrected_text: Optional[str] = None


class LocationPayload(BaseModel):
    # Either GPS coordinates (browser geolocation) or a free-text place
    # description (when geolocation is blocked/unavailable) - exactly one.
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_text: Optional[str] = None


def _session_or_404(session_id: str):
    try:
        return get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/conversation/describe")
async def conversation_describe(
    text: Optional[str] = Form(default=None),
    local_audio_path: Optional[str] = Form(default=None),
    audio: Optional[UploadFile] = File(default=None),
    source_language: Optional[str] = Form(default=None),
):
    """Turn 1: citizen describes the problem (voice or text)."""
    if not text and not local_audio_path and not audio:
        raise HTTPException(
            status_code=422,
            detail="Provide 'text', a recorded/uploaded 'audio' file, or 'local_audio_path'",
        )

    session = create_session()
    session.source_language = source_language

    if audio and not local_audio_path:
        audio_bytes = await audio.read()
        try:
            with _Stage("agent1 audio upload"):
                local_audio_path = await upload_audio_to_agent1(audio_bytes, audio.filename)
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Agent 1 audio upload failed: {exc}"
            ) from exc

    input_type = "audio" if local_audio_path else "text"

    try:
        with _Stage("agent1 webhook (ffmpeg + ASR + translate)"):
            agent1_result = await call_agent1(
                session.session_id,
                input_type,
                text=text,
                local_audio_path=local_audio_path,
                source_language=source_language,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 1 (language normalizer) failed: {exc}"
        ) from exc

    # Low ASR confidence doesn't hard-fail here - the transcript (however
    # rough) is shown back to the citizen at the confirm step, where they
    # can correct it. That's a better fit for a conversational flow than
    # rejecting outright.
    transcript = agent1_result.get("standardized_text") or ""
    raw_text = agent1_result.get("english_translation") or transcript or text
    if not raw_text:
        raise HTTPException(status_code=502, detail="Agent 1 returned no usable text")

    try:
        with _Stage("agent2 evidence/extract (Ollama C1 text AI)"):
            agent2_result = await call_agent2(session.session_id, raw_text)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 2 (evidence extractor) failed: {exc}"
        ) from exc

    structured = agent2_result["structured_evidence"]
    session.normalized_english = structured["normalized_english"]
    session.structured_evidence = structured

    warning = None
    if agent1_result.get("status") == "review_required":
        warning = (
            "Speech recognition wasn't confident about this recording - "
            "please check the text below carefully before confirming."
        )

    return {
        "session_id": session.session_id,
        "state": session.state,
        "understood_statement": structured["normalized_english"],
        "domain": structured["civic_domain"],
        "severity": structured["severity"],
        "suggested_track": structured["suggested_track"],
        "warning": warning,
        "message": f"Here's what I understood: \"{structured['normalized_english']}\". Is this correct?",
    }


@app.post("/conversation/{session_id}/confirm")
async def conversation_confirm(session_id: str, payload: ConfirmPayload):
    """Turn 2: citizen confirms or corrects the understood problem statement."""
    session = _session_or_404(session_id)

    if not payload.confirmed:
        if not payload.corrected_text:
            raise HTTPException(
                status_code=422,
                detail="corrected_text is required when confirmed is false",
            )
        try:
            agent2_result = await call_agent2(session.session_id, payload.corrected_text)
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Agent 2 (evidence extractor) failed: {exc}"
            ) from exc
        structured = agent2_result["structured_evidence"]
        session.normalized_english = structured["normalized_english"]
        session.structured_evidence = structured

    session.state = "awaiting_photo"
    return {
        "session_id": session.session_id,
        "state": session.state,
        "understood_statement": session.normalized_english,
        "message": "Thanks - now please take or upload a photo of the spot.",
    }


@app.post("/conversation/{session_id}/photo")
async def conversation_photo(
    session_id: str,
    image: UploadFile = File(...),
    device_lat: Optional[float] = Form(default=None),
    device_lon: Optional[float] = Form(default=None),
    device_timestamp: Optional[str] = Form(default=None),
    force: bool = Form(default=False),
):
    """Turn 3: citizen uploads a photo; the vision model checks it against
    the confirmed problem statement rather than trusting it blindly."""
    session = _session_or_404(session_id)
    if session.structured_evidence is None:
        raise HTTPException(
            status_code=409, detail="Describe the problem before attaching a photo"
        )

    image_bytes = await image.read()
    try:
        photo_result = await call_agent2_attach_photo(
            session.session_id,
            session.normalized_english,
            image_bytes=image_bytes,
            image_filename=image.filename,
            device_lat=device_lat,
            device_lon=device_lon,
            device_timestamp=device_timestamp,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 2 (evidence extractor) failed: {exc}"
        ) from exc

    visual = photo_result["visual_evidence"]
    if not visual["image_matches_report"] and not force:
        # Stay in awaiting_photo - let the citizen re-upload, or the UI can
        # resend this same call with force=true to proceed anyway.
        return {
            "session_id": session.session_id,
            "state": session.state,
            "photo_matches": False,
            "discrepancy_notes": visual.get("discrepancy_notes"),
            "message": (
                "This photo doesn't seem to match your description "
                f"(\"{session.normalized_english}\"): {visual.get('discrepancy_notes') or ''} "
                "Upload a different photo, or resubmit with force=true to continue anyway."
            ),
        }

    session.visual_evidence = visual
    session.geolocation = photo_result["geolocation"]

    latitude = session.geolocation.get("latitude")
    longitude = session.geolocation.get("longitude")
    if latitude is not None and longitude is not None:
        session.state = "ready"
        return {
            "session_id": session.session_id,
            "state": session.state,
            "photo_matches": visual["image_matches_report"],
            "message": "Got the photo and location. Ready to submit your report - please confirm.",
        }

    session.state = "awaiting_location"
    return {
        "session_id": session.session_id,
        "state": session.state,
        "photo_matches": visual["image_matches_report"],
        "message": (
            "Got the photo, but it has no location info. "
            "Please share your current location."
        ),
    }


@app.post("/conversation/{session_id}/location")
async def conversation_location(session_id: str, payload: LocationPayload):
    """Turn 4 (only if needed): citizen shares their location - either GPS
    coordinates, or a typed place description when geolocation is blocked
    (permission denied, corporate firewall/policy, desktop testing)."""
    session = _session_or_404(session_id)
    if session.state != "awaiting_location":
        raise HTTPException(
            status_code=409,
            detail=f"Location isn't needed right now (current state: {session.state})",
        )

    resolved_place = None
    if payload.latitude is not None and payload.longitude is not None:
        session.latitude = payload.latitude
        session.longitude = payload.longitude
    elif payload.address_text:
        match = await geocode_address(payload.address_text)
        if match is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Could not find a location matching \"{payload.address_text}\". "
                    "Try adding more detail (e.g. a nearby landmark, town, or district)."
                ),
            )
        session.latitude = match["latitude"]
        session.longitude = match["longitude"]
        resolved_place = match["display_name"]
    else:
        raise HTTPException(
            status_code=422, detail="Provide either latitude/longitude or address_text"
        )

    session.state = "ready"
    message = (
        f"Using location: {resolved_place}. If that's not the right spot, "
        "try a more specific description. Ready to submit your report - please confirm."
        if resolved_place
        else "Got your location. Ready to submit your report - please confirm."
    )
    return {
        "session_id": session.session_id,
        "state": session.state,
        "resolved_place": resolved_place,
        "message": message,
    }


@app.post("/conversation/{session_id}/finalize")
async def conversation_finalize(session_id: str):
    """Final turn: citizen confirms the summary and the ticket is raised."""
    session = _session_or_404(session_id)
    if session.state != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Not ready to submit yet (current state: {session.state})",
        )

    # dict.get(key, default) only falls back when the key is missing, not
    # when it's present but None (which is exactly the EXIF/no-device-geo
    # case) - use `or` so the manually-supplied location actually applies.
    latitude = (session.geolocation or {}).get("latitude") or session.latitude
    longitude = (session.geolocation or {}).get("longitude") or session.longitude

    ticket_payload = build_ticket_payload(
        session.structured_evidence,
        latitude,
        longitude,
        {
            "structured_evidence": session.structured_evidence,
            "geolocation": session.geolocation,
            "visual_evidence": session.visual_evidence,
        },
        settings.default_population_impact,
    )

    try:
        agent3_result = await call_agent3_ingest(ticket_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent 3 (triage & route) failed: {exc}"
        ) from exc

    session.ticket = agent3_result
    session.state = "completed"
    return {
        "session_id": session.session_id,
        "state": session.state,
        "ticket": agent3_result,
        "message": (
            f"Your report has been recorded as ticket #{agent3_result['ticket_id']} "
            "and is awaiting review."
        ),
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
