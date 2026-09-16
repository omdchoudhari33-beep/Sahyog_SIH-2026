"""G1 priority scoring and recalculation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings


def age_in_hours(created_at: datetime, now: datetime | None = None) -> float:
    """Return non-negative ticket age in hours, normalizing naive timestamps to UTC."""
    now = now or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max(0.0, (now - created_at).total_seconds() / 3600.0)


def calculate_priority_score(
    severity: float | None,
    cluster_count: int | None,
    age_hours: float,
    population_impact: float | None,
) -> float:
    """Apply the configured G1 weighted-sum formula."""
    score = (
        (severity or 0.0) * settings.PRIORITY_SEVERITY_WEIGHT
        + (cluster_count or 0) * settings.PRIORITY_CLUSTER_SIZE_WEIGHT
        + max(0.0, age_hours) * settings.PRIORITY_AGE_HOURS_WEIGHT
        + (population_impact or 0.0) * settings.PRIORITY_POPULATION_IMPACT_WEIGHT
    )
    return round(float(score), 6)


def recalculate_ticket_priority(db: Session, ticket_id: int) -> float:
    """Recalculate and persist one active ticket's priority score."""
    row = db.execute(
        text("""
            SELECT severity, cluster_count, created_at, population_impact
            FROM active_tickets
            WHERE id = :ticket_id
        """),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if row is None:
        raise ValueError(f"Active ticket {ticket_id} was not found")

    score = calculate_priority_score(
        severity=row["severity"],
        cluster_count=row["cluster_count"],
        age_hours=age_in_hours(row["created_at"]),
        population_impact=row["population_impact"],
    )
    db.execute(
        text("""
            UPDATE active_tickets
            SET priority_score = :priority_score,
                updated_at = now()
            WHERE id = :ticket_id
        """),
        {"priority_score": score, "ticket_id": ticket_id},
    )
    db.commit()
    return score


def recalculate_all_priorities(db: Session) -> int:
    """Recalculate every active ticket; return the number updated."""
    rows = db.execute(text("SELECT id FROM active_tickets WHERE status = 'active'")).scalars().all()
    for ticket_id in rows:
        recalculate_ticket_priority(db, ticket_id)
    return len(rows)
