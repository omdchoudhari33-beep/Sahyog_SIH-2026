"""Self-service HEI onboarding, same shape as 5.ULB Dispatch's onboarding.py.
Computes and stores the capability embedding at registration time so
matcher.py never needs to re-embed anything on the hot path. Also sets up
the University Portal login (app/auth.py) - see module docstring there for
why this is a real per-HEI password rather than a shared secret."""
from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import HeiCapability, HeiRegistry
from app.embedding import embed_text


def onboard_hei(
    db: Session, institution_name: str, state: str, district: str | None,
    contact_email: str, contact_phone: str | None, incubator_name: str | None,
    capacity_active_projects: int, domain: str, department_name: str, description: str,
    initial_password: str | None = None,
) -> tuple[HeiRegistry, HeiCapability, str]:
    """Returns (hei, capability, plaintext_password) - the plaintext is
    returned ONCE here so the admin doing onboarding can relay it to the
    HEI (email/phone/in person); it is never stored or logged anywhere,
    only its PBKDF2 hash is persisted."""
    plaintext_password = initial_password or secrets.token_urlsafe(9)

    hei = HeiRegistry(
        institution_name=institution_name, state=state, district=district,
        contact_email=contact_email, contact_phone=contact_phone,
        incubator_name=incubator_name, capacity_active_projects=capacity_active_projects,
        active=True, password_hash=hash_password(plaintext_password),
    )
    db.add(hei)
    db.flush()

    capability = HeiCapability(
        hei_id=hei.id, domain=domain.strip().upper(), department_name=department_name,
        description=description, embedding=embed_text(description), active=True,
    )
    db.add(capability)
    db.commit()
    db.refresh(hei)
    db.refresh(capability)
    return hei, capability, plaintext_password


def list_heis(db: Session) -> list[HeiRegistry]:
    return db.query(HeiRegistry).filter(HeiRegistry.active.is_(True)).order_by(HeiRegistry.institution_name).all()
