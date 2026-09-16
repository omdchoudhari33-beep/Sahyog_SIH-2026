from unittest.mock import MagicMock, patch

import pytest

from app.milestones import EVALUATION_PASS_THRESHOLD, evaluate_milestone, initialize_milestones, reconcile


def test_initialize_milestones_is_idempotent_when_already_present():
    db = MagicMock()
    existing = [MagicMock(id=1), MagicMock(id=2)]
    with patch("app.milestones.get_milestones", return_value=existing):
        result = initialize_milestones(db, proposal_id=1)
    assert result["created"] is False
    assert result["milestone_count"] == 2


def test_initialize_milestones_returns_not_found_when_no_proposal():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with patch("app.milestones.get_milestones", return_value=[]):
        result = initialize_milestones(db, proposal_id=1)
    assert result["created"] is False
    assert "was not found" in result["detail"]


def test_initialize_milestones_creates_three_milestones():
    db = MagicMock()
    proposal = MagicMock(timeline_weeks=12)
    db.query.return_value.filter.return_value.one_or_none.return_value = proposal
    with patch("app.milestones.get_milestones", return_value=[]):
        result = initialize_milestones(db, proposal_id=1)
    assert result["created"] is True
    assert result["milestone_count"] == 3
    assert db.commit.called


def test_evaluate_milestone_rejects_out_of_range_score():
    db = MagicMock()
    with pytest.raises(ValueError):
        evaluate_milestone(db, milestone_id=1, evaluator_name="x", score=1.5, notes=None)


def test_evaluate_milestone_raises_when_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(LookupError):
        evaluate_milestone(db, milestone_id=1, evaluator_name="x", score=0.5, notes=None)


def test_evaluate_milestone_sets_pass_above_threshold():
    db = MagicMock()
    milestone = MagicMock(status="pending")
    db.query.return_value.filter.return_value.one_or_none.return_value = milestone
    evaluate_milestone(db, milestone_id=1, evaluator_name="x", score=EVALUATION_PASS_THRESHOLD, notes=None)
    assert milestone.status == "evaluated_pass"


def test_evaluate_milestone_sets_fail_below_threshold():
    db = MagicMock()
    milestone = MagicMock(status="pending")
    db.query.return_value.filter.return_value.one_or_none.return_value = milestone
    evaluate_milestone(db, milestone_id=1, evaluator_name="x", score=EVALUATION_PASS_THRESHOLD - 0.1, notes=None)
    assert milestone.status == "evaluated_fail"


def test_reconcile_finds_and_initializes_missed_proposals():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [{"proposal_id": 10}, {"proposal_id": 11}]
    with patch("app.milestones.initialize_milestones", side_effect=[{"created": True}, {"created": False}]):
        result = reconcile(db)
    assert result["scanned"] == 2
    assert result["initialized"] == 1
    assert result["proposal_ids"] == [10, 11]
