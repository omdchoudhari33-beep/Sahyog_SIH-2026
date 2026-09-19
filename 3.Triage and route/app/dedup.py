"""
D2 Dedup Cluster Processing.

Pipeline per the diagram:
  1. Geospatial pass  - PostGIS radius query for nearby ACTIVE tickets
  2. Semantic pass    - if nearby tickets exist, embed the new statement
                        and compute cosine similarity against candidates
  3. Merge logic      - similarity > threshold -> merge into master ticket
                        (cluster_count += 1); else -> create new active ticket
"""
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import ActiveTicket
from app.embedding import embed_text
from app.schemas import IncomingTicket, DedupResult
from app.priority import recalculate_ticket_priority


def _vector_literal(vec: list[float]) -> str:
    """pgvector wants a string like '[0.1,0.2,...]' for parameter binding."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _geospatial_candidates(db: Session, lat: float, lon: float) -> list[int]:
    """
    Step 1: Geospatial Pass.
    Returns ids of active tickets within GEO_RADIUS_METERS of the new point,
    nearest first, capped at GEO_CANDIDATE_LIMIT.
    """
    rows = db.execute(
        text(
            """
            SELECT id
            FROM active_tickets
            WHERE status = 'active'
              AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
              )
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT :limit
            """
        ),
        {
            "lon": lon,
            "lat": lat,
            "radius_m": settings.GEO_RADIUS_METERS,
            "limit": settings.GEO_CANDIDATE_LIMIT,
        },
    ).fetchall()
    return [r[0] for r in rows]


def _best_semantic_match(
    db: Session, candidate_ids: list[int], new_embedding: list[float]
) -> Optional[tuple[int, float, int]]:
    """
    Step 2: Semantic Pass.
    Among the geospatial candidates, find the highest cosine similarity match.
    Returns (ticket_id, similarity, current_cluster_count) or None.
    pgvector's <=> operator returns cosine DISTANCE, so similarity = 1 - distance.
    """
    if not candidate_ids:
        return None

    rows = db.execute(
        text(
            """
            SELECT id, cluster_count, 1 - (embedding <=> :new_embedding) AS similarity
            FROM active_tickets
            WHERE id = ANY(:candidate_ids)
            ORDER BY similarity DESC
            LIMIT 1
            """
        ),
        {
            "new_embedding": _vector_literal(new_embedding),
            "candidate_ids": candidate_ids,
        },
    ).fetchone()

    if rows is None:
        return None
    return rows[0], rows[2], rows[1]


def process_incoming_ticket(db: Session, ticket: IncomingTicket) -> DedupResult:
    """
    Step 3: Merge Logic.
    Orchestrates the full D2 pipeline for one incoming (post-D1) ticket.
    """
    new_embedding = embed_text(ticket.standardized_problem_statement)

    candidate_ids = _geospatial_candidates(db, ticket.latitude, ticket.longitude)
    match = _best_semantic_match(db, candidate_ids, new_embedding) if candidate_ids else None

    if match is not None:
        master_id, similarity, current_count = match
        if similarity > settings.SIMILARITY_MERGE_THRESHOLD:
            # Merge into existing master ticket: increment cluster count,
            # bump severity/population_impact conservatively (take the max
            # reported so far), and refresh updated_at so G1 sees it as fresh.
            db.execute(
                text(
                    """
                    UPDATE active_tickets
                    SET cluster_count = cluster_count + 1,
                        severity = GREATEST(severity, :severity),
                        population_impact = GREATEST(population_impact, :population_impact),
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {
                    "id": master_id,
                    "severity": ticket.severity or 0.0,
                    "population_impact": ticket.population_impact or 0.0,
                },
            )
            db.commit()
            recalculate_ticket_priority(db, master_id)
            return DedupResult(
                action="merged",
                ticket_id=master_id,
                master_ticket_id=master_id,
                cluster_count=current_count + 1,
                similarity_score=round(similarity, 4),
            )

    # No candidates, or best match below threshold -> new master ticket.
    new_ticket = ActiveTicket(
        standardized_problem_statement=ticket.standardized_problem_statement,
        domain=ticket.domain,
        urgency=ticket.urgency,
        severity=ticket.severity or 0.0,
        population_impact=ticket.population_impact or 0.0,
        status="active",
        cluster_count=1,
        geom=f"SRID=4326;POINT({ticket.longitude} {ticket.latitude})",
        embedding=new_embedding,
        raw_evidence=ticket.raw_evidence,
        ai_suggested_track=ticket.ai_suggested_track,
        report_photo_media_id=ticket.report_photo_media_id,
        report_audio_media_id=ticket.report_audio_media_id,
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    recalculate_ticket_priority(db, new_ticket.id)

    best_similarity = round(match[1], 4) if match is not None else None
    return DedupResult(
        action="created_new",
        ticket_id=new_ticket.id,
        master_ticket_id=None,
        cluster_count=1,
        similarity_score=best_similarity,
    )
