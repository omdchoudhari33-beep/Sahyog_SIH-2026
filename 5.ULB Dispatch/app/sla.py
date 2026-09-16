"""Overdue scan + escalation. Business-hours math is computed in
Asia/Kolkata explicitly - all TIMESTAMPTZ columns are stored in UTC, and the
deployment server's local timezone is not guaranteed to be IST.

# TODO(human): plug in a real public-holiday calendar. Currently only
# Sat/Sun are excluded from business-hours counting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import Dispatch
from app.dispatch import _log_event, load_ticket_for_dispatch, send_dispatch
from app.router import resolve_contacts, NoContactForDomainError, NoUlbMatchError, AmbiguousUlbMatchError

IST = ZoneInfo("Asia/Kolkata")


def business_hours_elapsed(sent_at: datetime, now: datetime) -> float:
    """Business hours (Mon-Fri, all 24h of each such day for MVP simplicity)
    between sent_at and now, both converted to Asia/Kolkata first."""
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sent_ist = sent_at.astimezone(IST)
    now_ist = now.astimezone(IST)

    if now_ist <= sent_ist:
        return 0.0

    total_hours = 0.0
    cursor = sent_ist
    while cursor < now_ist:
        day_end = min(now_ist, cursor.replace(hour=23, minute=59, second=59, microsecond=999999) + timedelta(microseconds=1))
        if cursor.weekday() < 5:  # Mon=0 .. Fri=4
            total_hours += (day_end - cursor).total_seconds() / 3600.0
        cursor = day_end
    return total_hours


def _non_terminal_dispatches(db: Session) -> list[Dispatch]:
    return db.query(Dispatch).filter(Dispatch.status.notin_(["resolved", "disputed"])).all()


def _sla_hours_for(db: Session, domain: str | None, level: int) -> int | None:
    row = db.execute(
        text("SELECT sla_hours FROM escalation_matrix WHERE domain = :domain AND level = :level"),
        {"domain": domain or "", "level": level},
    ).mappings().one_or_none()
    return row["sla_hours"] if row else None


def scan_overdue(db: Session) -> int:
    """Escalates any dispatch whose business-hours age exceeds the
    escalation_matrix SLA for its (domain, level). Returns the number of
    dispatches escalated."""
    now = datetime.now(timezone.utc)
    escalated_count = 0

    for dispatch in _non_terminal_dispatches(db):
        ticket_row = db.execute(
            text("SELECT domain FROM active_tickets WHERE id = :ticket_id"),
            {"ticket_id": dispatch.ticket_id},
        ).mappings().one_or_none()
        if ticket_row is None:
            continue
        domain = ticket_row["domain"]

        sla_hours = _sla_hours_for(db, domain, dispatch.level)
        if sla_hours is None:
            continue

        elapsed = business_hours_elapsed(dispatch.sent_at, now)
        if elapsed < sla_hours:
            if dispatch.status == "sent":
                dispatch.status = "overdue" if elapsed >= sla_hours * 0.8 else dispatch.status
                db.add(dispatch)
                db.commit()
            continue

        _escalate(db, dispatch, domain)
        escalated_count += 1

    return escalated_count


def _escalate(db: Session, dispatch: Dispatch, domain: str | None) -> None:
    new_level = dispatch.level + 1

    try:
        # Same resolve_contacts() the initial-dispatch path uses, per spec -
        # keeps the domain -> catch-all fallback logic in exactly one place.
        contacts = resolve_contacts(db, dispatch.ticket_id, level=new_level)
    except (NoUlbMatchError, AmbiguousUlbMatchError, NoContactForDomainError):
        _log_event(db, dispatch.id, "escalated", "system", payload={"note": f"no level {new_level} contact configured - cannot escalate further"})
        db.commit()
        return

    next_contact = next((c for c in contacts if c.channel == "api"), contacts[0])

    # Mark the OLD row terminal-for-this-level FIRST and commit, so the new
    # INSERT below doesn't collide with uq_dispatches_ticket_active (that
    # index only allows one non-('resolved','disputed') row per ticket).
    dispatch.status = "escalated"
    db.add(dispatch)
    db.commit()
    _log_event(db, dispatch.id, "escalated", "system", payload={"new_level": new_level, "new_contact_id": next_contact.id})

    try:
        ticket = load_ticket_for_dispatch(db, dispatch.ticket_id)
    except LookupError:
        return

    send_dispatch(db, ticket, next_contact, level=new_level)


def scan_overdue_count_only(db: Session) -> int:
    """Read-only variant for tests/dashboards that just want a count without mutating state."""
    now = datetime.now(timezone.utc)
    count = 0
    for dispatch in _non_terminal_dispatches(db):
        ticket_row = db.execute(
            text("SELECT domain FROM active_tickets WHERE id = :ticket_id"),
            {"ticket_id": dispatch.ticket_id},
        ).mappings().one_or_none()
        if ticket_row is None:
            continue
        sla_hours = _sla_hours_for(db, ticket_row["domain"], dispatch.level)
        if sla_hours is None:
            continue
        if business_hours_elapsed(dispatch.sent_at, now) >= sla_hours:
            count += 1
    return count
