from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app import matcher as matcher_module
from app.matcher import TicketForMatch, create_match, decide_match, reconcile


def _ticket():
    return TicketForMatch(id=1, domain="ROADS_BRIDGES", standardized_problem_statement="Pothole", embedding=[0.1] * 384)


def test_create_match_is_idempotent_when_active_match_exists():
    db = MagicMock()
    existing = MagicMock(id=5, status="proposed")
    with patch.object(matcher_module, "get_active_match", return_value=existing):
        result = create_match(db, ticket_id=1)
    assert result["created"] is False
    assert result["match"] is existing


def test_create_match_returns_no_match_when_no_capability_fits():
    db = MagicMock()
    with patch.object(matcher_module, "get_active_match", return_value=None), \
         patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "_best_capability", return_value=None):
        db.execute.return_value.fetchall.return_value = []
        result = create_match(db, ticket_id=1)
    assert result["created"] is False
    assert "no HEI capability match" in result["detail"]


def test_create_match_sends_notification_and_commits():
    db = MagicMock()
    best = {"hei_id": 1, "capability_id": 1, "contact_email": "hei@example.com", "institution_name": "Demo HEI", "similarity": 0.8}
    inserted = MagicMock(id=1, match_token="tok123")
    with patch.object(matcher_module, "get_active_match", return_value=None), \
         patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "_best_capability", return_value=best), \
         patch.object(matcher_module, "_insert_match_row", return_value=inserted), \
         patch.object(matcher_module, "send_hei_notification", return_value={"success": True, "dry_run": True}) as mock_notify:
        db.execute.return_value.fetchall.return_value = []
        result = create_match(db, ticket_id=1)

    assert result["created"] is True
    mock_notify.assert_called_once()
    assert db.commit.called


def test_decide_match_accept_sets_status():
    db = MagicMock()
    match = MagicMock(status="proposed", ticket_id=1, attempt_no=1)
    with patch.object(matcher_module, "resolve_match_token", return_value=match):
        result = decide_match(db, "tok", "accept")
    assert match.status == "accepted"
    assert result["re_routed"] is False


def test_decide_match_decline_reroutes_to_next_hei():
    db = MagicMock()
    match = MagicMock(status="proposed", ticket_id=1, attempt_no=1)
    new_match = MagicMock(id=2)
    with patch.object(matcher_module, "resolve_match_token", return_value=match), \
         patch.object(matcher_module, "create_match", return_value={"created": True, "match": new_match}) as mock_create:
        result = decide_match(db, "tok", "decline", reason="Not our area")
    assert match.status == "declined"
    assert match.decline_reason == "Not our area"
    mock_create.assert_called_once_with(db, 1)
    assert result["re_routed"] is True


def test_decide_match_stops_after_max_attempts():
    db = MagicMock()
    match = MagicMock(status="proposed", ticket_id=1, attempt_no=5)
    with patch.object(matcher_module, "resolve_match_token", return_value=match), \
         patch.object(matcher_module.settings, "MAX_HEI_MATCH_ATTEMPTS", 5):
        result = decide_match(db, "tok", "decline")
    assert result["re_routed"] is False
    assert "human ops review" in result["detail"]


def test_reconcile_finds_and_matches_missed_tickets():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [{"ticket_id": 10}, {"ticket_id": 11}]
    with patch.object(matcher_module, "create_match", side_effect=[{"created": True}, {"created": False}]):
        result = reconcile(db)
    assert result["scanned"] == 2
    assert result["matched"] == 1
    assert result["ticket_ids"] == [10, 11]


def test_insert_match_row_returns_existing_on_uniqueness_collision():
    db = MagicMock()
    best = {"hei_id": 1, "capability_id": 1, "contact_email": "a@b.com", "institution_name": "X", "similarity": 0.5}
    existing = MagicMock(id=42, status="proposed")

    db.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate key value violates unique constraint \"uq_hei_matches_ticket_active\""))

    with patch.object(matcher_module, "get_active_match", return_value=existing):
        result = matcher_module._insert_match_row(db, ticket_id=1, best=best, attempt_no=1)

    assert result is existing
