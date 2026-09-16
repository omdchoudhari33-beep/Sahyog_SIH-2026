"""Self-service ULB contact onboarding form logic (GET/POST /admin/onboard).

This is the intended way ulb_contacts gets populated for this MVP - not a
placeholder for a "real" scraped-data mechanism to be built later. See
README "ULB data reality" section.

# TODO(human): before any real deployment, replace the trust-on-registration
# shortcut below with an actual verification step (e.g. OTP to
# officer_phone, or a signed link sent to a .gov.in email) - trusting
# self-submitted contact info unverified is a demo-only shortcut and must
# not reach production, since closure.py's verify_closure() treats
# verified_at as a trust signal for auto-resolving tickets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db import UlbContact, UlbDirectory


def list_ulbs(db: Session) -> list[UlbDirectory]:
    return db.query(UlbDirectory).filter(UlbDirectory.active.is_(True)).order_by(UlbDirectory.name).all()


def onboard_contact(
    db: Session,
    ulb_id: int,
    domain: Optional[str],
    dept_name: str,
    officer_name: Optional[str],
    officer_phone: Optional[str],
    email: str,
    channel: str = "email",
) -> UlbContact:
    ulb = db.query(UlbDirectory).filter(UlbDirectory.id == ulb_id, UlbDirectory.active.is_(True)).one_or_none()
    if ulb is None:
        raise LookupError(f"ULB {ulb_id} was not found or is not active")

    normalized_domain = (domain or "").strip().upper() or None

    contact = UlbContact(
        ulb_id=ulb_id,
        domain=normalized_domain,
        dept_name=dept_name,
        level=1,
        channel=channel,
        email=email,
        officer_name=officer_name,
        officer_phone=officer_phone,
        active=True,
        # Trust-on-registration - see module docstring TODO(human).
        verified_at=datetime.now(timezone.utc),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact
