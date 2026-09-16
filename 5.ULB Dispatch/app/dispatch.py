"""Orchestrates: pick contact -> pick adapter -> send -> log dispatch_events.

Idempotency and the circuit breaker rule live here. The real guarantee
against duplicate active dispatches under concurrency is the
uq_dispatches_ticket_active partial unique index (schema_002) - the
SELECT-first check in create_dispatch() is a courtesy fast path only, not
the source of truth.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.api_adapter import ApiAdapter
from app.adapters.email_adapter import EmailAdapter
from app.config import settings
from app.db import Dispatch, DispatchEvent, UlbContact
from app.router import (
    AmbiguousUlbMatchError,
    NoContactForDomainError,
    NoUlbMatchError,
    resolve_contacts,
)
from app.status_links import create_status_link

_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"  # unambiguous base32-ish


def _generate_correlation_code(ticket_id: int) -> str:
    suffix = "".join(random.choices(_CODE_ALPHABET, k=6))
    return f"SAHYOG-{ticket_id}-{suffix}"


@dataclass
class TicketForDispatch:
    id: int
    domain: Optional[str]
    standardized_problem_statement: str
    severity: Optional[float]
    population_impact: Optional[float]
    lat: Optional[float]
    lon: Optional[float]


def load_ticket_for_dispatch(db: Session, ticket_id: int) -> TicketForDispatch:
    row = db.execute(
        text(
            "SELECT id, domain, standardized_problem_statement, severity, population_impact, "
            "ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon "
            "FROM active_tickets WHERE id = :ticket_id"
        ),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if row is None:
        raise LookupError(f"active_tickets row {ticket_id} was not found")
    return TicketForDispatch(
        id=row["id"],
        domain=row["domain"],
        standardized_problem_statement=row["standardized_problem_statement"],
        severity=row["severity"],
        population_impact=row["population_impact"],
        lat=row["lat"],
        lon=row["lon"],
    )


def get_active_dispatch(db: Session, ticket_id: int) -> Optional[Dispatch]:
    return (
        db.query(Dispatch)
        .filter(Dispatch.ticket_id == ticket_id, Dispatch.status.notin_(["resolved", "disputed"]))
        .one_or_none()
    )


def _adapter_for_channel(channel: str):
    return ApiAdapter() if channel == "api" else EmailAdapter()


def consecutive_api_errors(db: Session, contact_id: int) -> int:
    """Counts consecutive most-recent api_error events across dispatches
    tied to this contact_id, stopping at the first non-api_error event."""
    rows = db.execute(
        text(
            """
            SELECT de.event_type
            FROM dispatch_events de
            JOIN dispatches d ON d.id = de.dispatch_id
            WHERE d.contact_id = :contact_id
            ORDER BY de.occurred_at DESC
            LIMIT 10
            """
        ),
        {"contact_id": contact_id},
    ).mappings().all()
    count = 0
    for r in rows:
        if r["event_type"] == "api_error":
            count += 1
        else:
            break
    return count


def _log_event(db: Session, dispatch_id: int, event_type: str, source: str, payload: dict | None = None) -> None:
    db.add(DispatchEvent(dispatch_id=dispatch_id, event_type=event_type, source=source, payload=payload))
    db.flush()


def pick_contact(db: Session, ticket_id: int, level: int, preferred_channel: str = "api") -> Optional[UlbContact]:
    """Circuit breaker: a contact whose channel is 'api' with >=3 consecutive
    api_error events is skipped in favor of an email-channel contact at the
    same ulb/domain/level, if one exists."""
    contacts = resolve_contacts(db, ticket_id, level=level)

    usable = [c for c in contacts if not (c.channel == "api" and consecutive_api_errors(db, c.id) >= 3)]
    if not usable:
        usable = contacts

    for c in usable:
        if c.channel == preferred_channel:
            return c
    return usable[0] if usable else None


def create_dispatch(db: Session, ticket_id: int) -> dict:
    existing = get_active_dispatch(db, ticket_id)
    if existing is not None:
        return {"ticket_id": ticket_id, "dispatch": existing, "created": False, "detail": "active dispatch already exists"}

    try:
        ticket = load_ticket_for_dispatch(db, ticket_id)
    except LookupError as exc:
        return {"ticket_id": ticket_id, "dispatch": None, "created": False, "detail": str(exc)}

    try:
        contact = pick_contact(db, ticket_id, level=1, preferred_channel="api")
    except (NoUlbMatchError, AmbiguousUlbMatchError, NoContactForDomainError) as exc:
        return {"ticket_id": ticket_id, "dispatch": None, "created": False, "detail": f"routing failed: {exc}"}

    if contact is None:
        return {"ticket_id": ticket_id, "dispatch": None, "created": False, "detail": "no usable contact found"}

    return send_dispatch(db, ticket, contact, level=1)


def send_dispatch(db: Session, ticket: TicketForDispatch, contact: UlbContact, level: int) -> dict:
    max_attempts = max(1, settings.DISPATCH_MAX_RETRIES)
    channel = contact.channel
    dispatch: Optional[Dispatch] = None
    last_error: Optional[str] = None

    for attempt_no in range(1, max_attempts + 1):
        dispatch = _insert_dispatch_row(db, ticket, contact, channel, level, attempt_no)
        if dispatch is None:
            last_error = "failed to allocate a unique correlation_code after 5 attempts"
            continue
        if dispatch.id is None:
            # Concurrent call already created the active dispatch for this ticket.
            return {"ticket_id": ticket.id, "dispatch": dispatch, "created": False, "detail": "created concurrently by another call"}

        token, status_link_url = create_status_link(db, dispatch.id)
        adapter = _adapter_for_channel(channel)
        result = adapter.send(contact=contact, ticket=ticket, correlation_code=dispatch.correlation_code, status_link_url=status_link_url)

        if result["success"]:
            _log_event(db, dispatch.id, "sent", "email" if channel == "email" else "api", payload=result.get("raw_response"))
            db.commit()
            return {"ticket_id": ticket.id, "dispatch": dispatch, "created": True, "detail": None}

        last_error = result.get("error")
        _log_event(db, dispatch.id, "api_error", "email" if channel == "email" else "api", payload={"error": last_error, "attempt_no": attempt_no})
        db.commit()

        if channel == "api":
            fallback_result = _try_email_fallback(db, ticket, dispatch, level, status_link_url)
            if fallback_result is not None:
                return fallback_result

        if attempt_no < max_attempts and not settings.DEBUG:
            time.sleep(settings.DISPATCH_RETRY_BACKOFF_SECONDS)

    # All retries exhausted (or api->email fallback also failed): status
    # stays 'sent' with the failure trail in dispatch_events per spec,
    # flagged for human ops review rather than silently dropped.
    return {"ticket_id": ticket.id, "dispatch": dispatch, "created": dispatch is not None, "detail": f"send failed after retries: {last_error}"}


def _insert_dispatch_row(db: Session, ticket: TicketForDispatch, contact: UlbContact, channel: str, level: int, attempt_no: int) -> Optional[Dispatch]:
    for _ in range(5):
        correlation_code = _generate_correlation_code(ticket.id)
        dispatch = Dispatch(
            ticket_id=ticket.id,
            ulb_id=contact.ulb_id,
            contact_id=contact.id,
            channel=channel,
            correlation_code=correlation_code,
            status="sent",
            level=level,
            attempt_no=attempt_no,
        )
        db.add(dispatch)
        try:
            db.flush()
            return dispatch
        except IntegrityError as exc:
            db.rollback()
            message = str(getattr(exc, "orig", exc))
            if "correlation_code" in message:
                continue  # collision - regenerate and retry
            # Otherwise this is uq_dispatches_ticket_active - another
            # concurrent call already won; surface that existing row.
            existing = get_active_dispatch(db, ticket.id)
            if existing is not None:
                placeholder = Dispatch(
                    id=None, ticket_id=existing.ticket_id, ulb_id=existing.ulb_id,
                    contact_id=existing.contact_id, channel=existing.channel,
                    correlation_code=existing.correlation_code, status=existing.status,
                    level=existing.level, attempt_no=existing.attempt_no,
                )
                return existing if existing.id is not None else placeholder
            raise
    return None


def _try_email_fallback(db: Session, ticket: TicketForDispatch, dispatch: Dispatch, level: int, status_link_url: str) -> Optional[dict]:
    try:
        contacts = resolve_contacts(db, ticket.id, level=level)
    except Exception:  # noqa: BLE001
        contacts = []
    email_contact = next((c for c in contacts if c.channel == "email"), None)

    if email_contact is None:
        _log_event(
            db, dispatch.id, "api_error", "system",
            payload={"note": "no email fallback contact configured for this ulb/domain/level - flagged for human ops review"},
        )
        db.commit()
        return None

    _log_event(
        db, dispatch.id, "api_error", "system",
        payload={"note": "demoting to email channel after api failure", "new_contact_id": email_contact.id},
    )
    dispatch.channel = "email"
    dispatch.contact_id = email_contact.id
    db.add(dispatch)
    db.commit()

    result = EmailAdapter().send(contact=email_contact, ticket=ticket, correlation_code=dispatch.correlation_code, status_link_url=status_link_url)
    if result["success"]:
        _log_event(db, dispatch.id, "sent", "email", payload=result.get("raw_response"))
        db.commit()
        return {"ticket_id": ticket.id, "dispatch": dispatch, "created": True, "detail": "sent via email fallback after api failure"}

    _log_event(db, dispatch.id, "api_error", "email", payload={"error": result.get("error"), "note": "email fallback also failed"})
    db.commit()
    return None


def reconcile(db: Session) -> dict:
    """Safety net for the fire-and-forget webhook in 3.Triage and route's
    apply_operator_decision: finds any decision='track_a' ticket with no
    row in dispatches at all, and dispatches it."""
    rows = db.execute(
        text(
            """
            SELECT vd.ticket_id
            FROM validation_decisions vd
            LEFT JOIN dispatches d ON d.ticket_id = vd.ticket_id
            WHERE vd.decision = 'track_a' AND d.id IS NULL
            """
        )
    ).mappings().all()

    ticket_ids = [r["ticket_id"] for r in rows]
    dispatched = 0
    for ticket_id in ticket_ids:
        result = create_dispatch(db, ticket_id)
        if result.get("created"):
            dispatched += 1
    return {"scanned": len(ticket_ids), "dispatched": dispatched, "ticket_ids": ticket_ids}
