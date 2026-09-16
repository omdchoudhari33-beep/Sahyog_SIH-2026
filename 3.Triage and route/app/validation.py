"""DNO human validation gate: read prioritized tickets and persist operator decisions."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

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
}
TRACK_B_DOMAINS = {
    "AGRICULTURAL_DISEASE", "UNKNOWN_STRUCTURAL_FAILURE",
    "ILLEGAL_CONSTRUCTION_ENCROACHMENT",
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


def _ticket_query() -> str:
    return """
        SELECT id, master_ticket_id, standardized_problem_statement, domain, urgency,
               severity, population_impact, status, cluster_count, priority_score,
               ai_suggested_track, created_at, updated_at
        FROM active_tickets
        WHERE status = 'active'
        ORDER BY priority_score DESC NULLS LAST, updated_at DESC, id ASC
        LIMIT :limit OFFSET :offset
    """


def list_prioritized_tickets(db: Session, limit: int, offset: int) -> list[dict[str, Any]]:
    rows = db.execute(text(_ticket_query()), {"limit": limit, "offset": offset}).mappings().all()
    return [_serialize_ticket(row) for row in rows]


def get_prioritized_ticket(db: Session, ticket_id: int) -> dict[str, Any] | None:
    row = db.execute(text("""SELECT id, master_ticket_id, standardized_problem_statement, domain, urgency, severity, population_impact, status, cluster_count, priority_score, ai_suggested_track, created_at, updated_at FROM active_tickets WHERE status = 'active' AND id = :ticket_id"""), {"ticket_id": ticket_id}).mappings().one_or_none()
    return _serialize_ticket(row) if row else None


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
