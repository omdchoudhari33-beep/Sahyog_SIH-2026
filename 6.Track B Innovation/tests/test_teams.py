from unittest.mock import MagicMock, patch

import pytest

from app.teams import form_team, nodal_decide, submit_proposal


def test_form_team_raises_when_match_not_accepted():
    db = MagicMock()
    match = MagicMock(status="proposed")
    db.query.return_value.filter.return_value.one_or_none.return_value = match
    with pytest.raises(ValueError):
        form_team(db, match_id=1, team_name="T", faculty_mentor_name="A", faculty_mentor_email="a@b.com", student_names=[])


def test_form_team_succeeds_when_match_accepted():
    db = MagicMock()
    match = MagicMock(status="accepted")
    db.query.return_value.filter.return_value.one_or_none.return_value = match
    team = form_team(db, match_id=1, team_name="T", faculty_mentor_name="A", faculty_mentor_email="a@b.com", student_names=["S1"])
    assert db.commit.called
    assert team.team_name == "T"


def test_submit_proposal_raises_when_team_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(LookupError):
        submit_proposal(db, team_id=1, title="T", summary="S", requested_budget=None, timeline_weeks=None)


def test_nodal_decide_rejects_invalid_decision():
    db = MagicMock()
    with pytest.raises(ValueError):
        nodal_decide(db, proposal_id=1, decision="bogus", nodal_officer_id="x", notes=None)


def test_nodal_decide_approval_notifies_downstream():
    db = MagicMock()
    proposal = MagicMock(id=1, status="submitted")
    db.query.return_value.filter.return_value.one_or_none.return_value = proposal
    with patch("app.teams._notify_downstream") as mock_notify:
        result = nodal_decide(db, proposal_id=1, decision="approved", nodal_officer_id="officer-1", notes="looks good")
    assert result.status == "approved"
    mock_notify.assert_called_once_with(1)


def test_nodal_decide_rejection_does_not_notify_downstream():
    db = MagicMock()
    proposal = MagicMock(id=1, status="submitted")
    db.query.return_value.filter.return_value.one_or_none.return_value = proposal
    with patch("app.teams._notify_downstream") as mock_notify:
        nodal_decide(db, proposal_id=1, decision="rejected", nodal_officer_id="officer-1", notes=None)
    mock_notify.assert_not_called()
