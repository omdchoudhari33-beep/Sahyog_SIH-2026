"""Fire-and-forget write to 9.Transparency Layer's audit log - same pattern
as 6.Track B Innovation's audit.py, duplicated rather than shared."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import settings


def log_audit_event(entity_type: str, entity_id: int, event: str, actor: Optional[str] = None, payload: Optional[dict[str, Any]] = None) -> None:
    try:
        httpx.post(
            f"{settings.TRANSPARENCY_BASE_URL.rstrip('/')}/audit/log",
            headers={"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN},
            json={"service_name": "7.Industry Partnership", "entity_type": entity_type, "entity_id": entity_id, "event": event, "actor": actor, "payload": payload},
            timeout=5.0,
        )
    except Exception:
        pass
