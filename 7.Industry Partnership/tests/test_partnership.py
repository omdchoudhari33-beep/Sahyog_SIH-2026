from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app import partnership as partnership_module
from app.partnership import ProposalForMatch, create_match, decide_match, reconcile


def _proposal():
    return ProposalForMatch(id=1, title="Pothole R&D pilot", summary="Fiber composite patching", domain="ROADS_BRIDGES")


def test_create_match_is_idempotent_when_active_match_exists():
    db = MagicMock()
    existing = MagicMock(id=5, status="proposed")
    with patch.object(partnership_module, "get_active_match", return_value=existing):
        result = create_match(db, proposal_id=1)
    assert result["created"] is False
    assert result["match"] is existing


def test_create_match_returns_no_match_when_no_partner_fits():
    db = MagicMock()
    with patch.object(partnership_module, "get_active_match", return_value=None), \
         patch.object(partnership_module, "load_proposal_for_match", return_value=_proposal()), \
         patch.object(partnership_module, "_best_partner", return_value=None):
        db.execute.return_value.fetchall.return_value = []
        result = create_match(db, proposal_id=1)
    assert result["created"] is False
    assert "no partner capability match" in result["detail"]


def test_create_match_sends_notification_and_commits():
    db = MagicMock()
    best = {"capability_id": 1, "partner_id": 1, "offering_type": "both", "name": "Demo Partner", "contact_email": "p@example.com"}
    inserted = MagicMock(id=1, match_token="tok", match_type="both")
    with patch.object(partnership_module, "get_active_match", return_value=None), \
         patch.object(partnership_module, "load_proposal_for_match", return_value=_proposal()), \
         patch.object(partnership_module, "_best_partner", return_value=best), \
         patch.object(partnership_module, "_insert_match_row", return_value=inserted), \
         patch.object(partnership_module, "send_partner_notification", return_value={"success": True, "dry_run": True}) as mock_notify:
        db.execute.return_value.fetchall.return_value = []
        result = create_match(db, proposal_id=1)
    assert result["created"] is True
    mock_notify.assert_called_once()
    assert db.commit.called


def test_decide_match_accept_sets_status():
    db = MagicMock()
    match = MagicMock(status="proposed", proposal_id=1)
    with patch.object(partnership_module, "resolve_match_token", return_value=match):
        result = decide_match(db, "tok", "accept")
    assert match.status == "accepted"
    assert result["re_routed"] is False


def test_decide_match_decline_reroutes():
    db = MagicMock()
    match = MagicMock(status="proposed", proposal_id=1)
    with patch.object(partnership_module, "resolve_match_token", return_value=match), \
         patch.object(partnership_module, "create_match", return_value={"created": True, "match": MagicMock(id=2)}) as mock_create:
        result = decide_match(db, "tok", "decline")
    assert match.status == "declined"
    mock_create.assert_called_once_with(db, 1)
    assert result["re_routed"] is True


def test_reconcile_finds_and_matches_missed_proposals():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [{"proposal_id": 10}, {"proposal_id": 11}]
    with patch.object(partnership_module, "create_match", side_effect=[{"created": True}, {"created": False}]):
        result = reconcile(db)
    assert result["scanned"] == 2
    assert result["matched"] == 1
    assert result["proposal_ids"] == [10, 11]


def test_insert_match_row_returns_existing_on_uniqueness_collision():
    db = MagicMock()
    best = {"capability_id": 1, "partner_id": 1, "offering_type": "mentorship", "name": "X", "contact_email": "a@b.com"}
    existing = MagicMock(id=42, status="proposed")
    db.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate key value violates unique constraint \"uq_partnership_matches_proposal_active\""))
    with patch.object(partnership_module, "get_active_match", return_value=existing):
        result = partnership_module._insert_match_row(db, proposal_id=1, best=best)
    assert result is existing
