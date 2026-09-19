"""Thin HTTP clients for the three Sahyog stage services."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional

import httpx

from app.config import settings


def _sign(body: bytes) -> str:
    return hmac.new(
        settings.agent1_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()


# Shared, reused across requests instead of opening a fresh httpx.AsyncClient
# (new TCP connection) on every single orchestrator -> agent call - that was
# adding a connection-setup tax on top of the real ASR/LLM/TTS latency on
# every hop of every turn.
_client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)


async def call_agent1(
    request_id: str,
    input_type: str,
    *,
    text: Optional[str] = None,
    local_audio_path: Optional[str] = None,
    source_language: Optional[str] = None,
) -> dict[str, Any]:
    """S1 Language Normalizer: PII scrub -> normalize -> ASR (if audio) -> translate."""
    body = {
        "request_id": request_id,
        "input_type": input_type,
        "text": text,
        "local_audio_path": local_audio_path,
        "source_language": source_language,
    }
    raw = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "X-Signature": _sign(raw)}

    response = await _client.post(
        f"{settings.agent1_base_url}/api/v1/webhook",
        content=raw,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


async def call_agent2(
    report_id: str,
    raw_text: str,
    *,
    image_bytes: Optional[bytes] = None,
    image_filename: Optional[str] = None,
    device_lat: Optional[float] = None,
    device_lon: Optional[float] = None,
    device_timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """S2 Evidence Extractor: text/geo/vision analysis via local Ollama models."""
    data: dict[str, str] = {"report_id": report_id, "raw_text": raw_text}
    if device_lat is not None:
        data["device_lat"] = str(device_lat)
    if device_lon is not None:
        data["device_lon"] = str(device_lon)
    if device_timestamp is not None:
        data["device_timestamp"] = device_timestamp

    files = None
    if image_bytes is not None:
        files = {
            "image": (
                image_filename or "evidence.jpg",
                image_bytes,
                "application/octet-stream",
            )
        }

    response = await _client.post(
        f"{settings.agent2_base_url}/evidence/extract",
        data=data,
        files=files,
    )
    response.raise_for_status()
    return response.json()


async def call_agent2_attach_photo(
    report_id: str,
    normalized_english: str,
    *,
    image_bytes: bytes,
    image_filename: Optional[str] = None,
    device_lat: Optional[float] = None,
    device_lon: Optional[float] = None,
    device_timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """S2 photo step: C2 (geo) + C3 (vision) against an already-classified
    report - does not re-run C1 text classification."""
    data: dict[str, str] = {"report_id": report_id, "normalized_english": normalized_english}
    if device_lat is not None:
        data["device_lat"] = str(device_lat)
    if device_lon is not None:
        data["device_lon"] = str(device_lon)
    if device_timestamp is not None:
        data["device_timestamp"] = device_timestamp

    files = {"image": (image_filename or "evidence.jpg", image_bytes, "application/octet-stream")}

    response = await _client.post(
        f"{settings.agent2_base_url}/evidence/attach-photo",
        data=data,
        files=files,
    )
    response.raise_for_status()
    return response.json()


async def call_agent3_ingest(ticket: dict[str, Any]) -> dict[str, Any]:
    """S3 Triage & Route: geospatial+semantic dedup, G1 priority, D4 track suggestion."""
    response = await _client.post(
        f"{settings.agent3_base_url}/d2/ingest", json=ticket
    )
    response.raise_for_status()
    return response.json()


async def upload_audio_to_agent1(audio_bytes: bytes, filename: Optional[str]) -> dict[str, Any]:
    """Hand raw audio bytes (e.g. a browser recording) to Agent 1 and get
    back a local_audio_path usable with call_agent1(), plus the durable
    object storage reference (media_id/media_url) Agent 1 persisted it
    under - see "1.Language normalizer/app/api/webhook.py"'s /audio/upload."""
    files = {"file": (filename or "recording.webm", audio_bytes, "application/octet-stream")}
    response = await _client.post(
        f"{settings.agent1_base_url}/api/v1/audio/upload", files=files
    )
    response.raise_for_status()
    return response.json()


async def list_agent3_tickets(limit: int, offset: int) -> dict[str, Any]:
    """Proxy for the DNO dashboard queue (avoids exposing Agent 3 to the browser directly)."""
    response = await _client.get(
        f"{settings.agent3_base_url}/dno/tickets",
        params={"limit": limit, "offset": offset},
    )
    response.raise_for_status()
    return response.json()


async def get_agent3_ticket(ticket_id: int) -> dict[str, Any]:
    """Proxy for the operator ticket detail view (same trust boundary as list_agent3_tickets)."""
    response = await _client.get(f"{settings.agent3_base_url}/dno/tickets/{ticket_id}")
    response.raise_for_status()
    return response.json()


async def call_agent1_speak(text: str, language: Optional[str]) -> Optional[bytes]:
    """S1 speech synthesis: translate (if needed) + TTS a system message.
    Returns None if speech isn't available for this language - callers must
    fall back to text-only, never treat this as required."""
    response = await _client.post(
        f"{settings.agent1_base_url}/api/v1/speak",
        json={"text": text, "language": language},
    )
    if response.status_code == 204:
        return None
    response.raise_for_status()
    return response.content


async def submit_agent3_decision(
    ticket_id: int, decision: str, operator_id: Optional[str], notes: Optional[str]
) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent3_base_url}/dno/tickets/{ticket_id}/decision",
        json={"decision": decision, "operator_id": operator_id, "notes": notes},
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Admin Portal proxies (services 5-9). Each downstream call carries
# X-Internal-Token - the Admin Portal's own HTTPBasic auth (ADMIN_FORM_PASSWORD)
# is what gates a human from reaching these routes at all; once past that
# gate, the orchestrator acts as a trusted internal caller on the admin's
# behalf, exactly like 6.Track B Innovation's nodal-review already did
# server-side against its own database. The browser never talks to agents
# 5-9 directly, same "proxied through the orchestrator" rule as agent 3.
# ---------------------------------------------------------------------------

def _internal_headers() -> dict[str, str]:
    return {"X-Internal-Token": settings.internal_service_token}


async def list_track_a_dispatches(limit: int = 50) -> dict[str, Any]:
    response = await _client.get(
        f"{settings.agent5_base_url}/dispatch", params={"limit": limit}, headers=_internal_headers()
    )
    response.raise_for_status()
    return response.json()


async def list_pending_proposals() -> dict[str, Any]:
    response = await _client.get(
        f"{settings.agent6_base_url}/trackb/proposals/pending", headers=_internal_headers()
    )
    response.raise_for_status()
    return response.json()


async def decide_nodal_proposal(proposal_id: int, decision: str, nodal_officer_id: str, notes: Optional[str]) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent6_base_url}/trackb/proposals/{proposal_id}/nodal-decision",
        headers=_internal_headers(),
        json={"decision": decision, "nodal_officer_id": nodal_officer_id, "notes": notes},
    )
    response.raise_for_status()
    return response.json()


async def list_fund_ledgers() -> dict[str, Any]:
    response = await _client.get(
        f"{settings.agent7_base_url}/partnership/ledgers", headers=_internal_headers()
    )
    response.raise_for_status()
    return response.json()


async def release_ledger_funds(ledger_id: int, amount: str, released_by: str, milestone_id: Optional[int]) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent7_base_url}/partnership/ledgers/{ledger_id}/release",
        headers=_internal_headers(),
        json={"amount": amount, "released_by": released_by, "milestone_id": milestone_id},
    )
    response.raise_for_status()
    return response.json()


async def list_pending_dispositions() -> dict[str, Any]:
    response = await _client.get(
        f"{settings.agent8_base_url}/lifecycle/pending-dispositions", headers=_internal_headers()
    )
    response.raise_for_status()
    return response.json()


async def apply_lifecycle_disposition(ticket_id: int, proposal_id: int, disposition: str, notes: Optional[str], startup_name: Optional[str], incubator_name: Optional[str]) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent8_base_url}/lifecycle/{ticket_id}/disposition",
        headers=_internal_headers(),
        json={"proposal_id": proposal_id, "disposition": disposition, "notes": notes, "startup_name": startup_name, "incubator_name": incubator_name},
    )
    response.raise_for_status()
    return response.json()


async def record_patent(ticket_id: int, proposal_id: int, title: str, applicant_names: list[str], filing_status: str, application_number: Optional[str], notes: Optional[str]) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent8_base_url}/lifecycle/{ticket_id}/patent",
        headers=_internal_headers(),
        json={
            "proposal_id": proposal_id, "title": title, "applicant_names": applicant_names,
            "filing_status": filing_status, "application_number": application_number, "notes": notes,
        },
    )
    response.raise_for_status()
    return response.json()


async def list_pending_matches() -> dict[str, Any]:
    response = await _client.get(
        f"{settings.agent6_base_url}/trackb/matches/pending", headers=_internal_headers()
    )
    response.raise_for_status()
    return response.json()


async def decide_trackb_match(match_id: int, decision: str, reason: Optional[str]) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent6_base_url}/trackb/matches/{match_id}/decide",
        headers=_internal_headers(),
        json={"decision": decision, "reason": reason},
    )
    response.raise_for_status()
    return response.json()


async def form_trackb_team(
    match_id: int, team_name: str, faculty_mentor_name: str, faculty_mentor_email: str, student_names: list[str]
) -> dict[str, Any]:
    response = await _client.post(
        f"{settings.agent6_base_url}/trackb/matches/{match_id}/team",
        headers=_internal_headers(),
        json={
            "team_name": team_name,
            "faculty_mentor_name": faculty_mentor_name,
            "faculty_mentor_email": faculty_mentor_email,
            "student_names": student_names,
        },
    )
    response.raise_for_status()
    return response.json()


async def submit_trackb_proposal(
    match_id: int,
    title: str,
    summary: str,
    *,
    requested_budget: Optional[float] = None,
    timeline_weeks: Optional[int] = None,
    solution_document_bytes: Optional[bytes] = None,
    solution_document_filename: Optional[str] = None,
) -> dict[str, Any]:
    """Forwards the citizen-portal's proposal form - including the solution
    PDF, if given - to Agent 6's internal-auth equivalent of its own
    /university/matches/{id}/proposal, the same multipart-forwarding shape
    call_agent2_attach_photo() above already uses for a photo upload."""
    data: dict[str, str] = {"title": title, "summary": summary}
    if requested_budget is not None:
        data["requested_budget"] = str(requested_budget)
    if timeline_weeks is not None:
        data["timeline_weeks"] = str(timeline_weeks)

    files = None
    if solution_document_bytes is not None:
        files = {"solution_document": (solution_document_filename or "solution.pdf", solution_document_bytes, "application/pdf")}

    response = await _client.post(
        f"{settings.agent6_base_url}/trackb/matches/{match_id}/proposal",
        headers=_internal_headers(),
        data=data,
        files=files,
    )
    response.raise_for_status()
    return response.json()


async def list_trackb_broadcast(ticket_id: int) -> dict[str, Any]:
    response = await _client.get(
        f"{settings.agent6_base_url}/trackb/{ticket_id}/broadcast", headers=_internal_headers()
    )
    response.raise_for_status()
    return response.json()


async def recalculate_agent3_priority(ticket_id: int) -> dict[str, Any]:
    response = await _client.post(f"{settings.agent3_base_url}/g1/recalculate/{ticket_id}")
    response.raise_for_status()
    return response.json()


async def get_transparency_dashboard() -> dict[str, Any]:
    # Public endpoint (X1 is intentionally unauthenticated - see
    # 9.Transparency Layer/README.md) - no internal token needed.
    response = await _client.get(f"{settings.agent9_base_url}/transparency/dashboard.json")
    response.raise_for_status()
    return response.json()
