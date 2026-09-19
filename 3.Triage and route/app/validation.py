"""DNO human validation gate: read prioritized tickets and persist operator decisions."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

# Fallback only - used when a ticket has no ai_suggested_track (e.g. it
# wasn't produced by the S2 Evidence Extractor). Domain values match S2's
# CivicDomain enum; kept upper-case since classify_ticket() normalizes to it.
TRACK_A_DOMAINS = {
    "ROADS", "ROADS_BRIDGES", "WASTE", "WASTE_GARBAGE_COLLECTION",
    "WATER_SUPPLY", "SANITATION_SEWAGE", "STREETLIGHTING",
    "DRAINAGE_WATERLOGGING", "PARKS_PUBLIC_SPACES", "TRAFFIC_SIGNAGE",
    "ENERGY_POWER", "STRAY_ANIMAL_MANAGEMENT",
    "HEALTHCARE_FACILITY_MAINTENANCE", "EDUCATION_FACILITY_MAINTENANCE",
    "CIVIC_DISASTER_EMERGENCY",
    # Near-always a known, fixable access barrier - same "routine fix"
    # shape as the municipal domains above, just not municipal.
    "ACCESSIBILITY_DISABILITY",
}
TRACK_B_DOMAINS = {
    "AGRICULTURAL_DISEASE", "UNKNOWN_STRUCTURAL_FAILURE",
    "ILLEGAL_CONSTRUCTION_ENCROACHMENT",
    # Systemic/research-shaped by nature - same reasoning as the three
    # domains above, just spanning agriculture/water/environment/
    # livelihoods instead of only civic infrastructure. HEALTHCARE_SERVICE_GAP
    # and PUBLIC_SERVICE_DELIVERY are deliberately left out of both sets -
    # genuinely ambiguous, so an ungoverned case falls through to
    # review_required for a human to decide, same as any other domain this
    # fallback doesn't recognize.
    "AGRICULTURE_LIVELIHOOD", "WATER_RESOURCE_MANAGEMENT",
    "RURAL_LIVELIHOODS", "ENVIRONMENT_POLLUTION",
}
VALID_DECISIONS = {"track_a", "track_b", "reject_merge"}


def classify_ticket(domain: str | None, urgency: str | None) -> str:
    """Deterministic D4 domain fallback; urgency is retained for future rules/audit."""
    normalized = (domain or "").strip().upper()
    if normalized in TRACK_A_DOMAINS:
        return "track_a"
    if normalized in TRACK_B_DOMAINS:
        return "track_b"
    return "review_required"


def _ticket_query(status_filter: str | None) -> str:
    # status_filter=None (the D4/operator queue's own use - see get_dno_tickets's
    # default below) means "only active", same as before this became
    # parameterized. status_filter="all" is the citizen-facing public feed's
    # case: the same endpoint, reused for a different audience with a
    # genuinely different scope - see that route's own docstring for why a
    # single hardcoded 'active' filter broke it (a ticket the DNO had
    # already triaged, i.e. every ticket that's actually progressed past
    # brand-new, silently vanished from the citizen feed the moment
    # operators did their job).
    where_clause = "WHERE t.status = 'active'" if status_filter != "all" else ""
    return f"""
        SELECT t.id, t.master_ticket_id, t.standardized_problem_statement, t.domain, t.urgency,
               t.severity, t.population_impact, t.status, t.cluster_count, t.priority_score,
               t.ai_suggested_track, t.created_at, t.updated_at,
               ST_Y(t.geom) AS lat, ST_X(t.geom) AS lon,
               photo.bucket AS photo_bucket, photo.object_key AS photo_object_key,
               audio.bucket AS audio_bucket, audio.object_key AS audio_object_key
        FROM active_tickets t
        LEFT JOIN media_objects photo ON photo.id = t.report_photo_media_id
        LEFT JOIN media_objects audio ON audio.id = t.report_audio_media_id
        {where_clause}
        ORDER BY t.priority_score DESC NULLS LAST, t.updated_at DESC, t.id ASC
        LIMIT :limit OFFSET :offset
    """


def _single_ticket_query() -> str:
    return """
        SELECT t.id, t.master_ticket_id, t.standardized_problem_statement, t.domain, t.urgency,
               t.severity, t.population_impact, t.status, t.cluster_count, t.priority_score,
               t.ai_suggested_track, t.created_at, t.updated_at,
               ST_Y(t.geom) AS lat, ST_X(t.geom) AS lon,
               photo.bucket AS photo_bucket, photo.object_key AS photo_object_key,
               audio.bucket AS audio_bucket, audio.object_key AS audio_object_key
        FROM active_tickets t
        LEFT JOIN media_objects photo ON photo.id = t.report_photo_media_id
        LEFT JOIN media_objects audio ON audio.id = t.report_audio_media_id
        WHERE t.status = 'active' AND t.id = :ticket_id
    """


def list_prioritized_tickets(db: Session, limit: int, offset: int, status_filter: str | None = None) -> list[dict[str, Any]]:
    rows = db.execute(text(_ticket_query(status_filter)), {"limit": limit, "offset": offset}).mappings().all()
    return [_serialize_ticket(row) for row in rows]


def get_prioritized_ticket(db: Session, ticket_id: int) -> dict[str, Any] | None:
    row = db.execute(text(_single_ticket_query()), {"ticket_id": ticket_id}).mappings().one_or_none()
    return _serialize_ticket(row) if row else None


def _media_url(bucket: str | None, object_key: str | None) -> str | None:
    if not bucket or not object_key:
        return None
    return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{bucket}/{object_key}"


def _serialize_ticket(row: Any) -> dict[str, Any]:
    ai_suggested_track = row["ai_suggested_track"]
    return {
        "ticket_id": row["id"],
        "master_ticket_id": row["master_ticket_id"],
        "problem_statement": row["standardized_problem_statement"],
        "domain": row["domain"],
        "urgency": row["urgency"],
        "severity": row["severity"],
        "population_impact": row["population_impact"],
        "status": row["status"],
        "cluster_count": row["cluster_count"],
        "priority_score": row["priority_score"],
        "ai_suggested_track": ai_suggested_track,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "suggested_track": ai_suggested_track or classify_ticket(row["domain"], row["urgency"]),
        "report_photo_url": _media_url(row["photo_bucket"], row["photo_object_key"]),
        "report_audio_url": _media_url(row["audio_bucket"], row["audio_object_key"]),
        "lat": row["lat"],
        "lon": row["lon"],
    }


def apply_operator_decision(
    db: Session,
    ticket_id: int,
    decision: str,
    operator_id: str | None,
    notes: str | None,
) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError("decision must be one of: track_a, track_b, reject_merge")

    row = db.execute(
        text("SELECT id, status FROM active_tickets WHERE id = :ticket_id FOR UPDATE"),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if row is None:
        raise LookupError(f"Active ticket {ticket_id} was not found")
    if row["status"] != "active":
        raise ValueError(f"Ticket {ticket_id} is not active (status={row['status']})")

    new_status = "merged" if decision == "reject_merge" else "validated"
    db.execute(
        text("""
            INSERT INTO validation_decisions
                (ticket_id, decision, operator_id, notes, created_at)
            VALUES (:ticket_id, :decision, :operator_id, :notes, now())
        """),
        {"ticket_id": ticket_id, "decision": decision, "operator_id": operator_id, "notes": notes},
    )
    db.execute(
        text("UPDATE active_tickets SET status = :status, updated_at = now() WHERE id = :ticket_id"),
        {"status": new_status, "ticket_id": ticket_id},
    )
    db.commit()

    if decision == "track_a":
        try:
            httpx.post(
                f"{os.getenv('ULB_DISPATCH_BASE_URL', 'http://localhost:8004')}/dispatch/{ticket_id}",
                headers={"X-Internal-Token": os.getenv("INTERNAL_SERVICE_TOKEN", "")},
                timeout=5.0,
            )
        except Exception:
            # Never let a Dispatch-service outage block or fail the DNO
            # validation decision itself. The Dispatch service has its own
            # backfill/reconciliation job that picks up any validated
            # track_a ticket with no dispatches row (see 5.ULB Dispatch/README.md).
            pass

    if decision == "track_b":
        try:
            httpx.post(
                f"{os.getenv('TRACKB_BASE_URL', 'http://localhost:8006')}/trackb/{ticket_id}",
                headers={"X-Internal-Token": os.getenv("INTERNAL_SERVICE_TOKEN", "")},
                timeout=5.0,
            )
        except Exception:
            # Same non-blocking guarantee as track_a above. Track B has its
            # own reconcile sweep for any validated track_b ticket with no
            # hei_matches row (see 6.Track B Innovation/README.md).
            pass

    return {
        "ticket_id": ticket_id,
        "decision": decision,
        "status": new_status,
        "operator_id": operator_id,
        "notes": notes,
        "decided_at": datetime.now(timezone.utc),
    }
