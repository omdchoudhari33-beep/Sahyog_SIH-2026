from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class MilestoneOut(BaseModel):
    id: int
    proposal_id: int
    sequence_no: int
    title: str
    description: Optional[str]
    target_date: Optional[date]
    status: str

    model_config = {"from_attributes": True}


class LifecycleAck(BaseModel):
    proposal_id: int
    milestone_count: int
    created: bool
    detail: Optional[str] = None


class ReconcileResult(BaseModel):
    scanned: int
    initialized: int
    proposal_ids: list[int]


class EvaluateRequest(BaseModel):
    evaluator_name: str
    score: float
    notes: Optional[str] = None


class PilotValidationOut(BaseModel):
    id: int
    ticket_id: int
    proposal_id: int
    geo_check_passed: Optional[bool]
    similarity_score: Optional[float]
    verdict: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DispositionRequest(BaseModel):
    proposal_id: int
    disposition: str  # 'handover' | 'spinout' | 'both'
    notes: Optional[str] = None
    startup_name: Optional[str] = None
    incubator_name: Optional[str] = None
