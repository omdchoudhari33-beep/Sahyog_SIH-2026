from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    service_name: str
    entity_type: str
    entity_id: int
    event: str
    actor: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class AuditLogOut(BaseModel):
    id: int
    service_name: str
    entity_type: str
    entity_id: int
    event: str
    actor: Optional[str]
    payload: Optional[dict[str, Any]]
    occurred_at: datetime

    model_config = {"from_attributes": True}
