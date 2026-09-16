"""Self-service partner onboarding, same shape as the other services'
onboarding.py modules."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import Partner, PartnerCapability

VALID_TYPES = {"industry", "msme", "startup", "csr", "lab"}
VALID_OFFERING_TYPES = {"mentorship", "sponsorship", "both"}


def onboard_partner(
    db: Session, name: str, type_: str, sector: str | None, contact_name: str | None,
    contact_email: str, contact_phone: str | None, domain: str, offering_type: str,
) -> tuple[Partner, PartnerCapability]:
    if type_ not in VALID_TYPES:
        raise ValueError(f"type must be one of: {', '.join(sorted(VALID_TYPES))}")
    if offering_type not in VALID_OFFERING_TYPES:
        raise ValueError(f"offering_type must be one of: {', '.join(sorted(VALID_OFFERING_TYPES))}")

    partner = Partner(name=name, type=type_, sector=sector, contact_name=contact_name, contact_email=contact_email, contact_phone=contact_phone, active=True)
    db.add(partner)
    db.flush()

    capability = PartnerCapability(partner_id=partner.id, domain=domain.strip().upper(), offering_type=offering_type, active=True)
    db.add(capability)
    db.commit()
    db.refresh(partner)
    db.refresh(capability)
    return partner, capability
