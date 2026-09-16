"""ULB + contact resolution: point-in-polygon lookup, then domain -> catch-all
contact fallback. See README "ULB data reality" section - the catch-all
(domain IS NULL) branch is the common case, not an edge case."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import UlbContact


class NoUlbMatchError(Exception):
    """No active ulb_directory polygon contains this ticket's location."""


class AmbiguousUlbMatchError(Exception):
    """More than one active ulb_directory polygon contains this ticket's
    location - overlapping boundaries must be fixed at the data level, this
    service will not silently guess which one is authoritative."""


class NoContactForDomainError(Exception):
    """Neither a domain-specific nor a catch-all contact exists for this
    ULB/level. Only raised once the catch-all fallback has also failed."""


def _load_ticket_geom_and_domain(db: Session, ticket_id: int) -> tuple[str, str | None]:
    row = db.execute(
        text("SELECT domain, geom FROM active_tickets WHERE id = :ticket_id"),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if row is None:
        raise LookupError(f"active_tickets row {ticket_id} was not found")
    return row["geom"], row["domain"]


def _resolve_ulb_id(db: Session, geom_wkb: str) -> int:
    rows = db.execute(
        text(
            "SELECT id FROM ulb_directory "
            "WHERE active AND ST_Contains(boundary, :geom)"
        ),
        {"geom": geom_wkb},
    ).mappings().all()
    if len(rows) == 0:
        raise NoUlbMatchError("No active ULB boundary contains this ticket's location")
    if len(rows) > 1:
        raise AmbiguousUlbMatchError(
            f"{len(rows)} active ULB boundaries contain this ticket's location "
            f"(ulb_ids={[r['id'] for r in rows]}) - overlapping boundary data must be fixed"
        )
    return rows[0]["id"]


def resolve_contacts(db: Session, ticket_id: int, level: int = 1) -> list[UlbContact]:
    """Returns all active ulb_contacts rows matching this ticket's ULB/level,
    preferring exact-domain rows over the catch-all (domain IS NULL) row
    when both exist. Returns a LIST (not a single contact) so dispatch.py
    can choose between api/email channels and so the circuit breaker
    (Step 7) can fall back to whichever channel is available.

    Raises NoUlbMatchError / AmbiguousUlbMatchError / NoContactForDomainError
    (never silently guesses or returns an empty list on error paths).
    """
    geom_wkb, domain = _load_ticket_geom_and_domain(db, ticket_id)
    ulb_id = _resolve_ulb_id(db, geom_wkb)

    rows = db.execute(
        text(
            """
            SELECT id, ulb_id, domain, dept_name, level, channel, email,
                   api_endpoint, api_key_ref, officer_name, officer_phone,
                   verified_at, active, created_at
            FROM ulb_contacts
            WHERE ulb_id = :ulb_id AND level = :level AND active
              AND (domain = :domain OR domain IS NULL)
            ORDER BY (domain IS NOT NULL) DESC
            """
        ),
        {"ulb_id": ulb_id, "level": level, "domain": domain},
    ).mappings().all()

    if not rows:
        raise NoContactForDomainError(
            f"No contact configured for ulb_id={ulb_id} domain={domain!r} level={level} "
            "(checked both exact-domain and catch-all)"
        )

    # Keep only the rows at whichever specificity tier won (all exact-domain
    # rows if any exist, otherwise all catch-all rows) - mirrors the ORDER BY.
    top_tier_is_domain_specific = rows[0]["domain"] is not None
    winning_rows = [
        r for r in rows
        if (r["domain"] is not None) == top_tier_is_domain_specific
    ]

    contact_ids = [r["id"] for r in winning_rows]
    contacts: Sequence[UlbContact] = (
        db.query(UlbContact).filter(UlbContact.id.in_(contact_ids)).all()
    )
    # Preserve the exact-domain-preferred ordering from the raw SQL above.
    by_id = {c.id: c for c in contacts}
    return [by_id[cid] for cid in contact_ids if cid in by_id]
