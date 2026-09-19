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

from app.config import settings


def _media_url(bucket: Optional[str], object_key: Optional[str]) -> Optional[str]:
    if not bucket or not object_key:
        return None
    return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{bucket}/{object_key}"


def get_unified_status(db: Session, ticket_id: int) -> Optional[dict[str, Any]]:
    ticket = db.execute(
        text(
            """
            SELECT t.id, t.domain, t.status, t.standardized_problem_statement, t.ai_suggested_track,
                   photo.bucket AS photo_bucket, photo.object_key AS photo_object_key
            FROM active_tickets t
            LEFT JOIN media_objects photo ON photo.id = t.report_photo_media_id
            WHERE t.id = :ticket_id
            """
        ),
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
        # The citizen's own submitted evidence photo - lets them confirm this
        # is really their report, and lets them see what was recorded even
        # before any human/institution has acted on it.
        "report_photo_url": _media_url(ticket["photo_bucket"], ticket["photo_object_key"]),
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
            track_a = dict(dispatch)
            # Real proof-of-work photo the field officer submitted at
            # closure, not the citizen's original report photo above - this
            # is the institution's (ULB officer's) own evidence that the
            # issue was actually fixed, sourced live from closure_proofs.
            closure = db.execute(
                text(
                    "SELECT photo_url, verified_at, citizen_confirmed FROM closure_proofs "
                    "WHERE ticket_id = :ticket_id ORDER BY created_at DESC LIMIT 1"
                ),
                {"ticket_id": ticket_id},
            ).mappings().one_or_none()
            if closure is not None:
                track_a["closure_photo_url"] = closure["photo_url"]
                track_a["closure_verified_at"] = closure["verified_at"]
                track_a["citizen_confirmed"] = closure["citizen_confirmed"]
            result["track_a"] = track_a

    elif decision["decision"] == "track_b":
        match = db.execute(
            text(
                """
                SELECT hm.status, hm.similarity_score, hm.created_at, hr.institution_name
                FROM hei_matches hm
                JOIN hei_registry hr ON hr.id = hm.hei_id
                WHERE hm.ticket_id = :ticket_id
                ORDER BY hm.created_at DESC LIMIT 1
                """
            ),
            {"ticket_id": ticket_id},
        ).mappings().one_or_none()
        proposal = db.execute(
            text("SELECT id, status, title FROM proposals WHERE ticket_id = :ticket_id ORDER BY submitted_at DESC LIMIT 1"),
            {"ticket_id": ticket_id},
        ).mappings().one_or_none()

        # The top-N HEIs this ticket's problem brief was broadcast to (see
        # 6.Track B Innovation's matcher.py::broadcast_to_top_n) - lets the
        # citizen see "sent to N universities, 1 has accepted" instead of
        # only the single currently-active match above.
        candidates = db.execute(
            text(
                """
                SELECT hr.institution_name, n.rank, hm.status AS match_status
                FROM hei_broadcast_notices n
                JOIN hei_registry hr ON hr.id = n.hei_id
                LEFT JOIN hei_matches hm ON hm.ticket_id = n.ticket_id AND hm.hei_id = n.hei_id
                WHERE n.ticket_id = :ticket_id
                ORDER BY n.rank
                """
            ),
            {"ticket_id": ticket_id},
        ).mappings().all()

        track_b: dict[str, Any] = {
            "match": dict(match) if match else None,
            "proposal": dict(proposal) if proposal else None,
            "candidates": [dict(c) for c in candidates],
        }

        if proposal is not None:
            milestones = db.execute(
                text("SELECT title, status FROM milestones WHERE proposal_id = :proposal_id ORDER BY sequence_no"),
                {"proposal_id": proposal["id"]},
            ).mappings().all()
            track_b["milestones"] = [dict(m) for m in milestones]

            pilot = db.execute(
                text(
                    "SELECT verdict, created_at, photo_url FROM pilot_validations "
                    "WHERE ticket_id = :ticket_id ORDER BY created_at DESC LIMIT 1"
                ),
                {"ticket_id": ticket_id},
            ).mappings().one_or_none()
            track_b["pilot_validation"] = dict(pilot) if pilot else None

        result["track_b"] = track_b

    return result
