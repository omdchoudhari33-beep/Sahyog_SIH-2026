"""X3 Immutable Audit Log. Append-only by application convention - this
service never exposes an UPDATE or DELETE route for audit_log, and none of
its own code issues one. See README for what "immutable" does and doesn't
mean here."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import AuditLog


def log_event(db: Session, service_name: str, entity_type: str, entity_id: int, event: str, actor: Optional[str] = None, payload: Optional[dict[str, Any]] = None) -> AuditLog:
    entry = AuditLog(service_name=service_name, entity_type=entity_type, entity_id=entity_id, event=event, actor=actor, payload=payload)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entries_for_entity(db: Session, entity_type: str, entity_id: int) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.occurred_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# X3 read side. audit_log.entity_id has no FK (entity_type varies: "ticket",
# "proposal", "milestone_fund_ledger" - see the real call sites in services
# 6/7/8) so there's no single join. All services share one Postgres instance
# ("dno_triage" - see DATABASE.md), the same way 6.Track B Innovation and
# 7.Industry Partnership each already declare their own read-only mirror of
# active_tickets/proposals - so this does the same via raw SQL rather than
# adding ORM models this service doesn't otherwise need.
# ---------------------------------------------------------------------------

_EVENT_SUMMARIES = {
    "hei_matched": lambda p: f"Matched to HEI #{p.get('hei_id', '?')} ({float(p.get('similarity_score') or 0):.0%} confidence, attempt {p.get('attempt_no', 1)})",
    "nodal_approved": lambda p: "Proposal approved by nodal officer" + (f" — {p['notes']}" if p.get("notes") else ""),
    "nodal_rejected": lambda p: "Proposal rejected by nodal officer" + (f" — {p['notes']}" if p.get("notes") else ""),
    "nodal_revision_requested": lambda p: "Revision requested by nodal officer" + (f" — {p['notes']}" if p.get("notes") else ""),
    "funds_released": lambda p: f"₹{p.get('amount', '?')} released (ledger status: {p.get('new_status', '?')})",
    "disposition_applied": lambda p: (
        f"Disposition recorded: {p.get('disposition', '?')}"
        + (f" (handover #{p['handover_id']})" if p.get("handover_id") else "")
        + (f" (spin-out #{p['spinout_id']})" if p.get("spinout_id") else "")
    ),
}


def summarize_event(event: str, payload: Optional[dict[str, Any]]) -> str:
    """Human-readable "action taken" line derived from the real logged
    event+payload - not a stored field, since most events don't carry a
    free-text outcome of their own."""
    template = _EVENT_SUMMARIES.get(event)
    if template:
        try:
            return template(payload or {})
        except Exception:
            pass
    return event.replace("_", " ").capitalize()


def list_audit_events(
    db: Session,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    service_name: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)
    if service_name:
        query = query.filter(AuditLog.service_name == service_name)
    if from_date:
        query = query.filter(AuditLog.occurred_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.occurred_at <= to_date)
    rows = query.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit).all()

    ticket_ids = {r.entity_id for r in rows if r.entity_type == "ticket"}
    proposal_ids = {r.entity_id for r in rows if r.entity_type == "proposal"}
    ledger_ids = {r.entity_id for r in rows if r.entity_type == "milestone_fund_ledger"}

    ledger_to_proposal: dict[int, int] = {}
    if ledger_ids:
        for row in db.execute(
            text("SELECT id, proposal_id FROM milestone_fund_ledger WHERE id = ANY(:ids)"), {"ids": list(ledger_ids)}
        ).mappings():
            ledger_to_proposal[row["id"]] = row["proposal_id"]
        proposal_ids |= set(ledger_to_proposal.values())

    proposal_info: dict[int, dict[str, Any]] = {}
    if proposal_ids:
        for row in db.execute(
            text("SELECT id, ticket_id, title, summary FROM proposals WHERE id = ANY(:ids)"), {"ids": list(proposal_ids)}
        ).mappings():
            proposal_info[row["id"]] = dict(row)
        ticket_ids |= {p["ticket_id"] for p in proposal_info.values()}

    ticket_info: dict[int, dict[str, Any]] = {}
    if ticket_ids:
        for row in db.execute(
            text("SELECT id, domain, standardized_problem_statement FROM active_tickets WHERE id = ANY(:ids)"),
            {"ids": list(ticket_ids)},
        ).mappings():
            ticket_info[row["id"]] = dict(row)

    results: list[dict[str, Any]] = []
    for r in rows:
        domain = None
        description = None
        if r.entity_type == "ticket":
            t = ticket_info.get(r.entity_id)
            if t:
                domain = t["domain"]
                description = t["standardized_problem_statement"]
        elif r.entity_type == "proposal":
            p = proposal_info.get(r.entity_id)
            if p:
                description = p["title"] + (f" — {p['summary']}" if p.get("summary") else "")
                t = ticket_info.get(p["ticket_id"])
                if t:
                    domain = t["domain"]
        elif r.entity_type == "milestone_fund_ledger":
            proposal_id = ledger_to_proposal.get(r.entity_id)
            p = proposal_info.get(proposal_id) if proposal_id else None
            if p:
                description = p["title"]
                t = ticket_info.get(p["ticket_id"])
                if t:
                    domain = t["domain"]

        results.append(
            {
                "id": r.id,
                "service_name": r.service_name,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "event": r.event,
                "actor": r.actor,
                "payload": r.payload,
                "occurred_at": r.occurred_at,
                "domain": domain,
                "description": description,
                "action_summary": summarize_event(r.event, r.payload),
            }
        )
    return results
