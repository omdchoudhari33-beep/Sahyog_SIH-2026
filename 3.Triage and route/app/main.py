from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import (
    IncomingTicket, DedupResult, PrioritizedTicket, TicketPage,
    OperatorDecision, DecisionResult,
)
from app.dedup import process_incoming_ticket
from app.embedding import get_embedding_model
from app.priority import recalculate_all_priorities, recalculate_ticket_priority
from app.validation import list_prioritized_tickets, get_prioritized_ticket, apply_operator_decision

app = FastAPI(title="Agent_D D2 + G1 + DNO Validation Service", version="0.3.0")
# Lets the citizen-portal Next.js app call this service straight from the
# browser. Origins come from FRONTEND_ORIGINS (comma-separated).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def warm_up_model():
    get_embedding_model()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/d2/ingest", response_model=DedupResult)
def ingest_ticket(ticket: IncomingTicket, db: Session = Depends(get_db)):
    return process_incoming_ticket(db, ticket)

@app.post("/g1/recalculate/{ticket_id}")
def recalculate_one(ticket_id: int, db: Session = Depends(get_db)):
    try:
        score = recalculate_ticket_priority(db, ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ticket_id": ticket_id, "priority_score": score}

@app.post("/g1/recalculate")
def recalculate_all(db: Session = Depends(get_db)):
    return {"updated_count": recalculate_all_priorities(db)}

@app.get("/dno/tickets", response_model=TicketPage)
def get_dno_tickets(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, description="'all' returns every ticket regardless of status; omitted/anything else means active-only."),
    db: Session = Depends(get_db),
):
    """Two audiences share this one route: the DNO/operator queue (default -
    active/untriaged tickets only, its actual job queue) and the
    citizen-portal's public home feed (status=all - every complaint
    regardless of where it is in the D4/Track A/B pipeline, not just the
    ones still awaiting a human decision). Ordered by G1 priority with D4
    suggestion either way."""
    return {"items": list_prioritized_tickets(db, limit, offset, status), "limit": limit, "offset": offset}

@app.get("/dno/tickets/{ticket_id}", response_model=PrioritizedTicket)
def get_dno_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = get_prioritized_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Active ticket {ticket_id} was not found")
    return ticket

@app.post("/dno/tickets/{ticket_id}/decision", response_model=DecisionResult, status_code=200)
def decide_dno_ticket(ticket_id: int, decision: OperatorDecision, db: Session = Depends(get_db)):
    """Persist Track A, Track B, or Reject-Merge and close the active queue item."""
    try:
        return apply_operator_decision(db, ticket_id, decision.decision, decision.operator_id, decision.notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
