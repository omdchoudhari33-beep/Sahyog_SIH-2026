"""Fire-and-forget write to 9.Transparency Layer's audit log - same
non-blocking pattern as every other cross-service call in this repo.
Duplicated per-service rather than shared, per this repo's "each service
stays independently deployable" idiom."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import settings


def log_audit_event(entity_type: str, entity_id: int, event: str, actor: Optional[str] = None, payload: Optional[dict[str, Any]] = None) -> None:
    try:
        httpx.post(
            f"{settings.TRANSPARENCY_BASE_URL.rstrip('/')}/audit/log",
            headers={"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN},
            json={"service_name": "6.Track B Innovation", "entity_type": entity_type, "entity_id": entity_id, "event": event, "actor": actor, "payload": payload},
            timeout=5.0,
        )
    except Exception:
        # Never let a Transparency Layer outage block the action that
        # triggered this log entry - there is no reconcile sweep for
        # missed audit events (see 9.Transparency Layer/README.md), an
        # acceptable gap for a best-effort observability log.
        pass
