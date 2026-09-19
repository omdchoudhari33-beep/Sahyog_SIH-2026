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


class HeiMatchWithTicketOut(HeiMatchOut):
    """Same as HeiMatchOut, plus the ticket's own domain/description - the
    institution portal's Match Inbox needs to show what the case is actually
    about, not just its id/similarity score."""

    ticket_domain: Optional[str] = None
    ticket_problem_statement: Optional[str] = None
    ticket_lat: Optional[float] = None
    ticket_lon: Optional[float] = None
    institution_name: Optional[str] = None


class BroadcastNoticeOut(BaseModel):
    id: int
    ticket_id: int
    hei_id: int
    institution_name: str
    rank: int
    similarity_score: float
    match_status: Optional[str] = None
    sent_at: datetime

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
    solution_document_media_id: Optional[int] = None
    solution_document_url: Optional[str] = None
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
