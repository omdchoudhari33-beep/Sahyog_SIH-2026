"""X3 Immutable Audit Log. Append-only by application convention - this
service never exposes an UPDATE or DELETE route for audit_log, and none of
its own code issues one. See README for what "immutable" does and doesn't
mean here."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db import AuditLog


def log_event(db: Session, service_name: str, entity_type: str, entity_id: int, event: str, actor: Optional[str] = None, payload: Optional[dict[str, Any]] = None) -> AuditLog:
    entry = AuditLog(service_name=service_name, entity_type=entity_type, entity_id=entity_id, event=event, actor=actor, payload=payload)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entries_for_entity(db: Session, entity_type: str, entity_id: int) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.occurred_at.asc())
        .all()
    )
