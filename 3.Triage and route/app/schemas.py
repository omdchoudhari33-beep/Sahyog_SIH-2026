from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

class IncomingTicket(BaseModel):
    standardized_problem_statement: str
    domain: Optional[str] = None
    urgency: Optional[str] = None
    severity: Optional[float] = 0.0
    population_impact: Optional[float] = 0.0
    latitude: float
    longitude: float
    raw_evidence: Optional[dict] = None
    # S2's own LLM-based track suggestion (considers complexity, not just
    # domain). Preferred over the D4 domain fallback when present.
    ai_suggested_track: Optional[Literal["track_a", "track_b", "review_required"]] = None

class DedupResult(BaseModel):
    action: Literal["created_new", "merged"]
    ticket_id: int
    master_ticket_id: Optional[int] = None
    cluster_count: int
    similarity_score: Optional[float] = Field(default=None)

class PrioritizedTicket(BaseModel):
    ticket_id: int
    master_ticket_id: Optional[int] = None
    problem_statement: str
    domain: Optional[str] = None
    urgency: Optional[str] = None
    severity: Optional[float] = None
    population_impact: Optional[float] = None
    status: str
    cluster_count: int
    priority_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ai_suggested_track: Optional[str] = None
    suggested_track: Literal["track_a", "track_b", "review_required"]

class TicketPage(BaseModel):
    items: list[PrioritizedTicket]
    limit: int
    offset: int

class OperatorDecision(BaseModel):
    decision: Literal["track_a", "track_b", "reject_merge"]
    operator_id: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = Field(default=None, max_length=4000)

class DecisionResult(BaseModel):
    ticket_id: int
    decision: Literal["track_a", "track_b", "reject_merge"]
    status: Literal["validated", "merged"]
    operator_id: Optional[str] = None
    notes: Optional[str] = None
    decided_at: datetime
