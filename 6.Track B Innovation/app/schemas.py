from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class HeiMatchOut(BaseModel):
    id: int
    ticket_id: int
    hei_id: int
    capability_id: Optional[int]
    similarity_score: Optional[float]
    status: str
    decline_reason: Optional[str]
    attempt_no: int
    decided_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackBAck(BaseModel):
    ticket_id: int
    match: Optional[HeiMatchOut] = None
    created: bool
    detail: Optional[str] = None


class ReconcileResult(BaseModel):
    scanned: int
    matched: int
    ticket_ids: list[int]


class TeamFormRequest(BaseModel):
    team_name: str
    faculty_mentor_name: str
    faculty_mentor_email: str
    student_names: list[str] = []


class ProposalSubmitRequest(BaseModel):
    title: str
    summary: str
    requested_budget: Optional[Decimal] = None
    timeline_weeks: Optional[int] = None


class ProposalOut(BaseModel):
    id: int
    team_id: int
    ticket_id: int
    title: str
    summary: str
    requested_budget: Optional[Decimal]
    timeline_weeks: Optional[int]
    status: str
    nodal_officer_id: Optional[str]
    nodal_notes: Optional[str]
    submitted_at: datetime
    decided_at: Optional[datetime]

    model_config = {"from_attributes": True}


class OnboardHeiForm(BaseModel):
    institution_name: str
    state: str
    district: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    incubator_name: Optional[str] = None
    capacity_active_projects: int = 3
    domain: str
    department_name: str
    description: str
