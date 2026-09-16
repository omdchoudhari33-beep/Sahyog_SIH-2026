"""F3 Handover to ULB/Panchayat + F4 Startup/Incubation Spin-out.

The disposition (handover vs spin-out vs both) is a human decision, never
auto-inferred from a pilot pass - see main.py's /admin/{ticket_id}/disposition.
"""
from __future__ import annotations

from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.config import settings
from app.db import HandoverRecord, RdOutcomeFeedback, SpinoutRecord


def record_handover(db: Session, ticket_id: int, notes: Optional[str]) -> HandoverRecord:
    """Reuses the ALREADY-BUILT 5.ULB Dispatch /dispatch/{ticket_id} endpoint
    rather than reinventing ULB contact routing - this is a fire-and-forget
    call like every other cross-service webhook in this repo, but its
    result IS captured (best-effort) since a human is waiting on this
    action's outcome, unlike the async decision-time webhooks."""
    ulb_dispatch_id = None
    try:
        response = httpx.post(
            f"{settings.ULB_DISPATCH_BASE_URL.rstrip('/')}/dispatch/{ticket_id}",
            headers={"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN},
            timeout=15.0,
        )
        if response.status_code == 200:
            body = response.json()
            dispatch = body.get("dispatch") or {}
            ulb_dispatch_id = dispatch.get("id")
    except Exception:  # noqa: BLE001 - the handover record itself must still be saved even if ULB Dispatch is unreachable
        pass

    record = HandoverRecord(ticket_id=ticket_id, ulb_dispatch_id=ulb_dispatch_id, handover_notes=notes)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def record_spinout(db: Session, proposal_id: int, startup_name: str, incubator_name: Optional[str], notes: Optional[str]) -> SpinoutRecord:
    record = SpinoutRecord(proposal_id=proposal_id, startup_name=startup_name, incubator_name=incubator_name, notes=notes)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def apply_disposition(
    db: Session, ticket_id: int, proposal_id: int, disposition: str, notes: Optional[str],
    startup_name: Optional[str], incubator_name: Optional[str],
) -> dict:
    if disposition not in ("handover", "spinout", "both"):
        raise ValueError("disposition must be one of: handover, spinout, both")

    result: dict = {"ticket_id": ticket_id, "proposal_id": proposal_id, "disposition": disposition}

    if disposition in ("handover", "both"):
        handover = record_handover(db, ticket_id, notes)
        result["handover_id"] = handover.id

    if disposition in ("spinout", "both"):
        if not startup_name:
            raise ValueError("startup_name is required for a spinout disposition")
        spinout = record_spinout(db, proposal_id, startup_name, incubator_name, notes)
        result["spinout_id"] = spinout.id
        db.add(RdOutcomeFeedback(ticket_id=ticket_id, outcome="spinout", notes=f"proposal_id={proposal_id}, startup_name={startup_name}"))
        db.commit()

    log_audit_event("ticket", ticket_id, "disposition_applied", payload=result)
    return result
