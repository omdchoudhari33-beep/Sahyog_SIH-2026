"""TB1 (semantic HEI matcher) + TB2 (accept/decline, decline -> re-route to
next-best HEI). Idempotency follows the exact same shape as 5.ULB Dispatch's
dispatch.py: uq_hei_matches_ticket_active is the real guarantee under
concurrency, the app-level check here is a courtesy fast path only.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.config import settings
from app.db import HeiMatch
from app.notify import send_hei_notification


def _vector_literal(vec: list[float]) -> str:
    """pgvector wants a string like '[0.1,0.2,...]' for parameter binding -
    same helper as 3.Triage and route's dedup.py."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


@dataclass
class TicketForMatch:
    id: int
    domain: Optional[str]
    standardized_problem_statement: str
    embedding: list[float]


def load_ticket_for_match(db: Session, ticket_id: int) -> TicketForMatch:
    row = db.execute(
        text("SELECT id, domain, standardized_problem_statement, embedding FROM active_tickets WHERE id = :ticket_id"),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if row is None:
        raise LookupError(f"active_tickets row {ticket_id} was not found")
    embedding = row["embedding"]
    if isinstance(embedding, str):
        embedding = [float(x) for x in embedding.strip("[]").split(",")]
    return TicketForMatch(id=row["id"], domain=row["domain"], standardized_problem_statement=row["standardized_problem_statement"], embedding=list(embedding))


def get_active_match(db: Session, ticket_id: int) -> Optional[HeiMatch]:
    return db.query(HeiMatch).filter(HeiMatch.ticket_id == ticket_id, HeiMatch.status == "proposed").one_or_none()


def _best_capability(db: Session, ticket: TicketForMatch, exclude_hei_ids: list[int]) -> Optional[dict]:
    """Semantic pass: cosine similarity between the ticket's (already
    computed, reused as-is) embedding and each active HEI capability's
    embedding. Also excludes HEIs at capacity - a simplification: only
    counts currently-accepted matches against capacity_active_projects,
    not proposals still in flight."""
    exclude_clause = "AND hc.hei_id != ALL(:exclude_hei_ids)" if exclude_hei_ids else ""
    rows = db.execute(
        text(
            f"""
            SELECT hc.id AS capability_id, hc.hei_id, hr.contact_email, hr.institution_name,
                   1 - (hc.embedding <=> :ticket_embedding) AS similarity
            FROM hei_capabilities hc
            JOIN hei_registry hr ON hr.id = hc.hei_id
            WHERE hc.active AND hr.active
              {exclude_clause}
              AND (
                    SELECT COUNT(*) FROM hei_matches m
                    WHERE m.hei_id = hc.hei_id AND m.status = 'accepted'
                  ) < hr.capacity_active_projects
            ORDER BY similarity DESC
            LIMIT 1
            """
        ),
        {"ticket_embedding": _vector_literal(ticket.embedding), "exclude_hei_ids": exclude_hei_ids or []},
    ).mappings().one_or_none()
    return dict(rows) if rows else None


def _insert_match_row(db: Session, ticket_id: int, best: dict, attempt_no: int) -> Optional[HeiMatch]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.MATCH_TOKEN_TTL_HOURS)
    match = HeiMatch(
        ticket_id=ticket_id,
        hei_id=best["hei_id"],
        capability_id=best["capability_id"],
        similarity_score=best["similarity"],
        status="proposed",
        attempt_no=attempt_no,
        match_token=token,
        token_expires_at=expires_at,
    )
    db.add(match)
    try:
        db.flush()
        return match
    except IntegrityError:
        db.rollback()
        existing = get_active_match(db, ticket_id)
        return existing


def create_match(db: Session, ticket_id: int) -> dict:
    existing = get_active_match(db, ticket_id)
    if existing is not None:
        return {"ticket_id": ticket_id, "match": existing, "created": False, "detail": "active match already exists"}

    try:
        ticket = load_ticket_for_match(db, ticket_id)
    except LookupError as exc:
        return {"ticket_id": ticket_id, "match": None, "created": False, "detail": str(exc)}

    prior_hei_ids = [
        r[0] for r in db.execute(
            text("SELECT DISTINCT hei_id FROM hei_matches WHERE ticket_id = :ticket_id AND status = 'declined'"),
            {"ticket_id": ticket_id},
        ).fetchall()
    ]
    best = _best_capability(db, ticket, exclude_hei_ids=prior_hei_ids)
    if best is None:
        return {"ticket_id": ticket_id, "match": None, "created": False, "detail": "no HEI capability match found (none available or all declined/at capacity)"}

    match = _insert_match_row(db, ticket_id, best, attempt_no=len(prior_hei_ids) + 1)
    if match is None or match.id is None:
        return {"ticket_id": ticket_id, "match": match, "created": False, "detail": "match already created concurrently"}

    decide_url = f"{settings.STATUS_LINK_BASE_URL.rstrip('/')}/hei/{match.match_token}"
    result = send_hei_notification(
        to_email=best["contact_email"], hei_name=best["institution_name"],
        ticket_problem_statement=ticket.standardized_problem_statement,
        similarity_score=best["similarity"], decide_url=decide_url,
    )
    db.commit()
    log_audit_event("ticket", ticket_id, "hei_matched", actor="system", payload={"hei_id": best["hei_id"], "similarity_score": best["similarity"], "attempt_no": match.attempt_no})
    return {"ticket_id": ticket_id, "match": match, "created": True, "detail": None, "notify": result}


def resolve_match_token(db: Session, token: str) -> HeiMatch:
    match = db.query(HeiMatch).filter(HeiMatch.match_token == token).one_or_none()
    if match is None:
        raise LookupError("match token not found")
    expires_at = match.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise TimeoutError("match token has expired")
    if match.status != "proposed":
        raise ValueError(f"match already decided (status={match.status})")
    return match


def apply_decision(db: Session, match: HeiMatch, decision: str, reason: Optional[str] = None) -> dict:
    """Core state transition, shared by both entry points: the token-based
    email link (decide_match below) and the session-authenticated
    University Portal (app/main.py's /university/matches/{id}/decide) - one
    code path so the two can never drift out of sync. Caller is responsible
    for authenticating/authorizing access to `match` before calling this.

    decision: 'accept' or 'decline'. On decline, auto re-routes to the
    next-best HEI (up to MAX_HEI_MATCH_ATTEMPTS), mirroring 5.ULB Dispatch's
    contact-fallback idiom in dispatch.py."""
    if match.status != "proposed":
        raise ValueError(f"match already decided (status={match.status})")

    if decision == "accept":
        match.status = "accepted"
        match.decided_at = datetime.now(timezone.utc)
        db.add(match)
        db.commit()
        return {"match": match, "re_routed": False}

    match.status = "declined"
    match.decline_reason = reason
    match.decided_at = datetime.now(timezone.utc)
    db.add(match)
    db.commit()

    if match.attempt_no >= settings.MAX_HEI_MATCH_ATTEMPTS:
        return {"match": match, "re_routed": False, "detail": "max HEI match attempts reached - flagged for human ops review"}

    reroute = create_match(db, match.ticket_id)
    return {"match": match, "re_routed": bool(reroute.get("created")), "new_match": reroute.get("match")}


def decide_match(db: Session, token: str, decision: str, reason: Optional[str] = None) -> dict:
    """Token-based entry point (email link) - resolves+validates the token,
    then delegates to apply_decision()."""
    match = resolve_match_token(db, token)
    return apply_decision(db, match, decision, reason)


def reconcile(db: Session) -> dict:
    """Safety net for the fire-and-forget webhook in 3.Triage and route's
    apply_operator_decision: finds any decision='track_b' ticket with no
    hei_matches row at all (first-ever attempt), and matches it."""
    rows = db.execute(
        text(
            """
            SELECT vd.ticket_id
            FROM validation_decisions vd
            LEFT JOIN hei_matches m ON m.ticket_id = vd.ticket_id
            WHERE vd.decision = 'track_b' AND m.id IS NULL
            """
        )
    ).mappings().all()

    ticket_ids = [r["ticket_id"] for r in rows]
    matched = 0
    for ticket_id in ticket_ids:
        result = create_match(db, ticket_id)
        if result.get("created"):
            matched += 1
    return {"scanned": len(ticket_ids), "matched": matched, "ticket_ids": ticket_ids}
