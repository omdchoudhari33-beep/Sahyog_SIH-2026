from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DispatchEventOut(BaseModel):
    id: int
    event_type: str
    payload: Optional[dict[str, Any]] = None
    source: str
    occurred_at: datetime

    model_config = {"from_attributes": True}


class DispatchOut(BaseModel):
    id: int
    ticket_id: int
    ulb_id: int
    contact_id: int
    channel: str
    correlation_code: str
    status: str
    level: int
    attempt_no: int
    sent_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DispatchDetail(BaseModel):
    dispatch: DispatchOut
    events: list[DispatchEventOut]


class DispatchAck(BaseModel):
    """Response body used by /dispatch/{ticket_id} - always a clean JSON
    body, never an unhandled exception, per the Step 7 contract."""

    ticket_id: int
    dispatch: Optional[DispatchOut] = None
    created: bool
    detail: Optional[str] = None


class ReconcileResult(BaseModel):
    scanned: int
    dispatched: int
    ticket_ids: list[int]


class StatusUpdateRequest(BaseModel):
    status: Literal["acked", "in_progress", "resolved"]


class OnboardContactForm(BaseModel):
    ulb_id: int
    domain: Optional[str] = None
    dept_name: str
    officer_name: Optional[str] = None
    officer_phone: Optional[str] = None
    email: str
    channel: Literal["api", "email"] = "email"


class OnboardResult(BaseModel):
    contact_id: int
    ulb_id: int
    domain: Optional[str]
    dept_name: str
    channel: str
    created: bool = True


class ClosureProofOut(BaseModel):
    id: int
    ticket_id: int
    dispatch_id: int
    geo_check_passed: Optional[bool]
    similarity_score: Optional[float]
    verified_at: Optional[datetime]

    model_config = {"from_attributes": True}
