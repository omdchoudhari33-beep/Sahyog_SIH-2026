"""I1 Partner Registry lookups + I2 Mentor & Sponsor Matching.

Matching is domain-keyword based (not semantic/embedding) - proposals don't
carry a domain column directly, so this reads it off the originating ticket
via the read-only active_tickets mirror. Simpler than Track B's semantic
matcher by design: partner capability taxonomies are much shallower than
free-text HEI department descriptions.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import ActiveTicket, PartnershipMatch, Proposal
from app.notify import send_partner_notification


@dataclass
class ProposalForMatch:
    id: int
    title: str
    summary: str
    domain: Optional[str]


def load_proposal_for_match(db: Session, proposal_id: int) -> ProposalForMatch:
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).one_or_none()
    if proposal is None:
        raise LookupError(f"proposals row {proposal_id} was not found")
    ticket = db.query(ActiveTicket).filter(ActiveTicket.id == proposal.ticket_id).one_or_none()
    return ProposalForMatch(id=proposal.id, title=proposal.title, summary=proposal.summary, domain=ticket.domain if ticket else None)


def get_active_match(db: Session, proposal_id: int) -> Optional[PartnershipMatch]:
    return db.query(PartnershipMatch).filter(PartnershipMatch.proposal_id == proposal_id, PartnershipMatch.status == "proposed").one_or_none()


def _best_partner(db: Session, domain: Optional[str], exclude_partner_ids: list[int]) -> Optional[dict]:
    exclude_clause = "AND pc.partner_id != ALL(:exclude_ids)" if exclude_partner_ids else ""
    rows = db.execute(
        text(
            f"""
            SELECT pc.id AS capability_id, pc.partner_id, pc.offering_type, p.name, p.contact_email
            FROM partner_capabilities pc
            JOIN partners p ON p.id = pc.partner_id
            WHERE pc.active AND p.active AND (pc.domain = :domain OR pc.domain = 'ANY')
              {exclude_clause}
            ORDER BY (pc.domain = :domain) DESC
            LIMIT 1
            """
        ),
        {"domain": domain or "", "exclude_ids": exclude_partner_ids or []},
    ).mappings().one_or_none()
    return dict(rows) if rows else None


def _insert_match_row(db: Session, proposal_id: int, best: dict) -> Optional[PartnershipMatch]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.MATCH_TOKEN_TTL_HOURS)
    match_type = "both" if best["offering_type"] == "both" else best["offering_type"]
    match = PartnershipMatch(
        proposal_id=proposal_id, partner_id=best["partner_id"], match_type=match_type,
        status="proposed", match_token=token, token_expires_at=expires_at,
    )
    db.add(match)
    try:
        db.flush()
        return match
    except IntegrityError:
        db.rollback()
        return get_active_match(db, proposal_id)


def create_match(db: Session, proposal_id: int) -> dict:
    existing = get_active_match(db, proposal_id)
    if existing is not None:
        return {"proposal_id": proposal_id, "match": existing, "created": False, "detail": "active match already exists"}

    try:
        proposal = load_proposal_for_match(db, proposal_id)
    except LookupError as exc:
        return {"proposal_id": proposal_id, "match": None, "created": False, "detail": str(exc)}

    prior_partner_ids = [
        r[0] for r in db.execute(
            text("SELECT DISTINCT partner_id FROM partnership_matches WHERE proposal_id = :proposal_id AND status = 'declined'"),
            {"proposal_id": proposal_id},
        ).fetchall()
    ]
    best = _best_partner(db, proposal.domain, exclude_partner_ids=prior_partner_ids)
    if best is None:
        return {"proposal_id": proposal_id, "match": None, "created": False, "detail": "no partner capability match found"}

    match = _insert_match_row(db, proposal_id, best)
    if match is None or match.id is None:
        return {"proposal_id": proposal_id, "match": match, "created": False, "detail": "match already created concurrently"}

    decide_url = f"{settings.STATUS_LINK_BASE_URL.rstrip('/')}/partner/{match.match_token}"
    notify = send_partner_notification(
        to_email=best["contact_email"], partner_name=best["name"], proposal_title=proposal.title,
        proposal_summary=proposal.summary, match_type=match.match_type, decide_url=decide_url,
    )
    db.commit()
    return {"proposal_id": proposal_id, "match": match, "created": True, "detail": None, "notify": notify}


def resolve_match_token(db: Session, token: str) -> PartnershipMatch:
    match = db.query(PartnershipMatch).filter(PartnershipMatch.match_token == token).one_or_none()
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


def decide_match(db: Session, token: str, decision: str) -> dict:
    match = resolve_match_token(db, token)
    if decision == "accept":
        match.status = "accepted"
        match.decided_at = datetime.now(timezone.utc)
        db.add(match)
        db.commit()
        return {"match": match, "re_routed": False}

    match.status = "declined"
    match.decided_at = datetime.now(timezone.utc)
    db.add(match)
    db.commit()
    reroute = create_match(db, match.proposal_id)
    return {"match": match, "re_routed": bool(reroute.get("created")), "new_match": reroute.get("match")}


def reconcile(db: Session) -> dict:
    """Safety net for the fire-and-forget webhook from 6.Track B Innovation
    (fired on nodal approval): finds any 'approved' proposal with no
    partnership_matches row at all, and matches it."""
    rows = db.execute(
        text(
            """
            SELECT pr.id AS proposal_id
            FROM proposals pr
            LEFT JOIN partnership_matches m ON m.proposal_id = pr.id
            WHERE pr.status = 'approved' AND m.id IS NULL
            """
        )
    ).mappings().all()

    proposal_ids = [r["proposal_id"] for r in rows]
    matched = 0
    for proposal_id in proposal_ids:
        result = create_match(db, proposal_id)
        if result.get("created"):
            matched += 1
    return {"scanned": len(proposal_ids), "matched": matched, "proposal_ids": proposal_ids}
