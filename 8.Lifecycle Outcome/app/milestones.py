"""F1 Milestone Tracker + Evaluator."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import Milestone, MilestoneEvaluation, Proposal

# TODO(human): 0.6 is a placeholder pass/fail cutoff, not a calibrated
# threshold - same caveat 3.Triage and route's SIMILARITY_MERGE_THRESHOLD
# carries for its own free-chosen number. Revisit against real evaluator
# data before relying on it.
EVALUATION_PASS_THRESHOLD = 0.6


def get_milestones(db: Session, proposal_id: int) -> list[Milestone]:
    return db.query(Milestone).filter(Milestone.proposal_id == proposal_id).order_by(Milestone.sequence_no).all()


def initialize_milestones(db: Session, proposal_id: int) -> dict:
    existing = get_milestones(db, proposal_id)
    if existing:
        return {"proposal_id": proposal_id, "milestone_count": len(existing), "created": False, "detail": "milestones already initialized"}

    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).one_or_none()
    if proposal is None:
        return {"proposal_id": proposal_id, "milestone_count": 0, "created": False, "detail": f"proposals row {proposal_id} was not found"}

    weeks = proposal.timeline_weeks or 12
    today = date.today()
    plan = [
        (1, "Kickoff", 0),
        (2, "Mid-point review", weeks // 2),
        (3, "Final delivery", weeks),
    ]
    for sequence_no, title, offset_weeks in plan:
        db.add(Milestone(
            proposal_id=proposal_id, sequence_no=sequence_no, title=title,
            target_date=today + timedelta(weeks=offset_weeks), status="pending",
        ))
    db.commit()
    return {"proposal_id": proposal_id, "milestone_count": len(plan), "created": True, "detail": None}


def evaluate_milestone(db: Session, milestone_id: int, evaluator_name: str, score: float, notes: Optional[str]) -> Milestone:
    if not (0.0 <= score <= 1.0):
        raise ValueError("score must be between 0.0 and 1.0")
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).one_or_none()
    if milestone is None:
        raise LookupError(f"milestone {milestone_id} was not found")

    db.add(MilestoneEvaluation(milestone_id=milestone_id, evaluator_name=evaluator_name, score=score, notes=notes))
    milestone.status = "evaluated_pass" if score >= EVALUATION_PASS_THRESHOLD else "evaluated_fail"
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


def reconcile(db: Session) -> dict:
    """Safety net for the fire-and-forget webhook from 6.Track B Innovation:
    finds any 'approved' proposal with no milestones row at all."""
    rows = db.execute(
        text(
            """
            SELECT pr.id AS proposal_id
            FROM proposals pr
            LEFT JOIN milestones m ON m.proposal_id = pr.id
            WHERE pr.status = 'approved' AND m.id IS NULL
            """
        )
    ).mappings().all()

    proposal_ids = [r["proposal_id"] for r in rows]
    initialized = 0
    for proposal_id in proposal_ids:
        result = initialize_milestones(db, proposal_id)
        if result.get("created"):
            initialized += 1
    return {"scanned": len(proposal_ids), "initialized": initialized, "proposal_ids": proposal_ids}
