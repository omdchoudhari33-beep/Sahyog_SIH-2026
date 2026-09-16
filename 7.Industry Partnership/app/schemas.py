from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class PartnershipMatchOut(BaseModel):
    id: int
    proposal_id: int
    partner_id: int
    match_type: str
    status: str
    decided_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class PartnershipAck(BaseModel):
    proposal_id: int
    match: Optional[PartnershipMatchOut] = None
    created: bool
    detail: Optional[str] = None


class ReconcileResult(BaseModel):
    scanned: int
    matched: int
    proposal_ids: list[int]


class LedgerOut(BaseModel):
    id: int
    proposal_id: int
    partner_id: Optional[int]
    total_committed_amount: Decimal
    currency: str
    status: str
    escrow_provider: Optional[str]

    model_config = {"from_attributes": True}


class FundReleaseRequest(BaseModel):
    amount: Decimal
    milestone_id: Optional[int] = None
    released_by: str


class OnboardPartnerForm(BaseModel):
    name: str
    type: str
    sector: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    domain: str
    offering_type: str = "mentorship"
