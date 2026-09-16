"""X2 Citizen Status Portal - unified lookup by ticket ID (the citizen's own
reference number, not a secret token - see README on why this is safe:
active_tickets rows carry no PII, and this only ever returns status/progress
fields, never contact details or internal routing data).

Real SMS/WhatsApp delivery of this link is TODO(human) - this only serves
the lookup page itself; the diagram's "ticket ID + SMS/WhatsApp" is the
citizen's channel for FINDING this page, not something this service
proactively sends yet.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_unified_status(db: Session, ticket_id: int) -> Optional[dict[str, Any]]:
    ticket = db.execute(
        text("SELECT id, domain, status, standardized_problem_statement, ai_suggested_track FROM active_tickets WHERE id = :ticket_id"),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if ticket is None:
        return None

    decision = db.execute(
        text("SELECT decision, created_at AS decided_at FROM validation_decisions WHERE ticket_id = :ticket_id ORDER BY created_at DESC LIMIT 1"),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()

    result: dict[str, Any] = {
        "ticket_id": ticket["id"],
        "domain": ticket["domain"],
        "status": ticket["status"],
        "problem_statement": ticket["standardized_problem_statement"],
        "track": decision["decision"] if decision else None,
        "track_a": None,
        "track_b": None,
    }

    if decision is None:
        return result

    if decision["decision"] == "track_a":
        dispatch = db.execute(
            text("SELECT status, correlation_code, sent_at FROM dispatches WHERE ticket_id = :ticket_id ORDER BY sent_at DESC LIMIT 1"),
            {"ticket_id": ticket_id},
        ).mappings().one_or_none()
        if dispatch is not None:
            result["track_a"] = dict(dispatch)

    elif decision["decision"] == "track_b":
        match = db.execute(
            text("SELECT status, similarity_score, created_at FROM hei_matches WHERE ticket_id = :ticket_id ORDER BY created_at DESC LIMIT 1"),
            {"ticket_id": ticket_id},
        ).mappings().one_or_none()
        proposal = db.execute(
            text("SELECT id, status, title FROM proposals WHERE ticket_id = :ticket_id ORDER BY submitted_at DESC LIMIT 1"),
            {"ticket_id": ticket_id},
        ).mappings().one_or_none()

        track_b: dict[str, Any] = {"match": dict(match) if match else None, "proposal": dict(proposal) if proposal else None}

        if proposal is not None:
            milestones = db.execute(
                text("SELECT title, status FROM milestones WHERE proposal_id = :proposal_id ORDER BY sequence_no"),
                {"proposal_id": proposal["id"]},
            ).mappings().all()
            track_b["milestones"] = [dict(m) for m in milestones]

            pilot = db.execute(
                text("SELECT verdict, created_at FROM pilot_validations WHERE ticket_id = :ticket_id ORDER BY created_at DESC LIMIT 1"),
                {"ticket_id": ticket_id},
            ).mappings().one_or_none()
            track_b["pilot_validation"] = dict(pilot) if pilot else None

        result["track_b"] = track_b

    return result
