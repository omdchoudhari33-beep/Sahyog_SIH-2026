"""TB3 Team Formation + TB4 Proposal Submission -> Nodal Approval."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.config import settings
from app.db import HeiMatch, Proposal, Team


def form_team(db: Session, match_id: int, team_name: str, faculty_mentor_name: str, faculty_mentor_email: str, student_names: list[str]) -> Team:
    match = db.query(HeiMatch).filter(HeiMatch.id == match_id).one_or_none()
    if match is None:
        raise LookupError(f"hei_matches row {match_id} was not found")
    if match.status != "accepted":
        raise ValueError(f"match {match_id} has not been accepted (status={match.status})")

    team = Team(
        match_id=match_id, team_name=team_name, faculty_mentor_name=faculty_mentor_name,
        faculty_mentor_email=faculty_mentor_email, student_names=student_names,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def submit_proposal(db: Session, team_id: int, title: str, summary: str, requested_budget, timeline_weeks: Optional[int]) -> Proposal:
    team = db.query(Team).filter(Team.id == team_id).one_or_none()
    if team is None:
        raise LookupError(f"team {team_id} was not found")
    match = db.query(HeiMatch).filter(HeiMatch.id == team.match_id).one_or_none()

    proposal = Proposal(
        team_id=team_id, ticket_id=match.ticket_id, title=title, summary=summary,
        requested_budget=requested_budget, timeline_weeks=timeline_weeks, status="submitted",
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def nodal_decide(db: Session, proposal_id: int, decision: str, nodal_officer_id: str, notes: Optional[str]) -> Proposal:
    """decision: 'approved' | 'rejected' | 'revision_requested'. On approval,
    fires fire-and-forget webhooks to Industry Partnership and Lifecycle
    Outcome, same non-blocking pattern as the track_a/track_b webhooks."""
    if decision not in ("approved", "rejected", "revision_requested"):
        raise ValueError("decision must be one of: approved, rejected, revision_requested")

    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).one_or_none()
    if proposal is None:
        raise LookupError(f"proposal {proposal_id} was not found")

    proposal.status = decision
    proposal.nodal_officer_id = nodal_officer_id
    proposal.nodal_notes = notes
    proposal.decided_at = datetime.now(timezone.utc)
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    log_audit_event("proposal", proposal_id, f"nodal_{decision}", actor=nodal_officer_id, payload={"notes": notes})

    if decision == "approved":
        _notify_downstream(proposal_id)

    return proposal


def _notify_downstream(proposal_id: int) -> None:
    headers = {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}
    targets = (
        f"{settings.INDUSTRY_PARTNERSHIP_BASE_URL.rstrip('/')}/partnership/proposal-approved/{proposal_id}",
        f"{settings.LIFECYCLE_OUTCOME_BASE_URL.rstrip('/')}/lifecycle/proposal-approved/{proposal_id}",
    )
    for url in targets:
        try:
            httpx.post(url, headers=headers, timeout=5.0)
        except Exception:
            # Never let a downstream-service outage block the nodal approval
            # itself - both services have their own reconcile sweep.
            pass
