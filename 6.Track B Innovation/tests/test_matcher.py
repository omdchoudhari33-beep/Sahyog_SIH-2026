from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app import matcher as matcher_module
from app.brief import TicketBrief
from app.matcher import TicketForMatch, broadcast_to_top_n, create_match, decide_match, reconcile, register_interest


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


def _brief():
    return TicketBrief(
        ticket_id=1, problem_statement="Pothole", domain="ROADS_BRIDGES", severity=0.6,
        population_impact=200.0, latitude=23.3, longitude=85.3, photo_url=None,
        generated_at=matcher_module.datetime.now(matcher_module.timezone.utc),
    )


def test_broadcast_to_top_n_sends_and_stores_one_notice_per_candidate():
    db = MagicMock()
    candidates = [
        {"hei_id": 1, "capability_id": 10, "institution_name": "BIT Mesra", "contact_email": "a@bitmesra.ac.in", "similarity": 0.9},
        {"hei_id": 2, "capability_id": 20, "institution_name": "NIT Jamshedpur", "contact_email": "b@nitjsr.ac.in", "similarity": 0.8},
    ]
    with patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "load_ticket_brief", return_value=_brief()), \
         patch.object(matcher_module, "_top_n_capabilities", return_value=candidates), \
         patch.object(matcher_module, "send_broadcast_brief", return_value={"success": True}) as mock_send:
        result = broadcast_to_top_n(db, ticket_id=1, n=10)

    assert result["sent"] == 2
    assert mock_send.call_count == 2
    assert db.add.call_count == 2
    assert db.commit.called


def test_broadcast_to_top_n_skips_duplicate_notice_without_failing():
    db = MagicMock()
    candidates = [
        {"hei_id": 1, "capability_id": 10, "institution_name": "BIT Mesra", "contact_email": "a@bitmesra.ac.in", "similarity": 0.9},
    ]
    db.flush.side_effect = IntegrityError("insert", {}, Exception('duplicate key value violates unique constraint "hei_broadcast_notices_ticket_id_hei_id_key"'))
    with patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "load_ticket_brief", return_value=_brief()), \
         patch.object(matcher_module, "_top_n_capabilities", return_value=candidates), \
         patch.object(matcher_module, "send_broadcast_brief") as mock_send:
        result = broadcast_to_top_n(db, ticket_id=1, n=10)

    assert result["sent"] == 0
    mock_send.assert_not_called()


def test_broadcast_to_top_n_returns_detail_when_brief_unavailable():
    db = MagicMock()
    with patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "load_ticket_brief", return_value=None):
        result = broadcast_to_top_n(db, ticket_id=1, n=10)

    assert result["sent"] == 0
    assert "brief unavailable" in result["detail"]


def test_create_match_broadcasts_on_first_attempt_only():
    db = MagicMock()
    best = {"hei_id": 1, "capability_id": 1, "contact_email": "hei@example.com", "institution_name": "Demo HEI", "similarity": 0.8}
    inserted = MagicMock(id=1, match_token="tok123", attempt_no=1)
    with patch.object(matcher_module, "get_active_match", return_value=None), \
         patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "_best_capability", return_value=best), \
         patch.object(matcher_module, "_insert_match_row", return_value=inserted), \
         patch.object(matcher_module, "send_hei_notification", return_value={"success": True, "dry_run": True}), \
         patch.object(matcher_module, "broadcast_to_top_n") as mock_broadcast:
        db.execute.return_value.fetchall.return_value = []
        create_match(db, ticket_id=1)

    mock_broadcast.assert_called_once_with(db, 1)


def test_create_match_does_not_rebroadcast_on_rerouted_attempt():
    db = MagicMock()
    best = {"hei_id": 2, "capability_id": 2, "contact_email": "hei2@example.com", "institution_name": "Second HEI", "similarity": 0.7}
    inserted = MagicMock(id=2, match_token="tok456", attempt_no=2)
    with patch.object(matcher_module, "get_active_match", return_value=None), \
         patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "_best_capability", return_value=best), \
         patch.object(matcher_module, "_insert_match_row", return_value=inserted), \
         patch.object(matcher_module, "send_hei_notification", return_value={"success": True, "dry_run": True}), \
         patch.object(matcher_module, "broadcast_to_top_n") as mock_broadcast:
        db.execute.return_value.fetchall.return_value = []
        create_match(db, ticket_id=1)

    mock_broadcast.assert_not_called()


def test_insert_match_row_returns_existing_on_uniqueness_collision():
    db = MagicMock()
    best = {"hei_id": 1, "capability_id": 1, "contact_email": "a@b.com", "institution_name": "X", "similarity": 0.5}
    existing = MagicMock(id=42, status="proposed")

    db.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate key value violates unique constraint \"uq_hei_matches_ticket_active\""))

    with patch.object(matcher_module, "get_active_match", return_value=existing):
        result = matcher_module._insert_match_row(db, ticket_id=1, best=best, attempt_no=1)

    assert result is existing


def test_register_interest_requires_a_broadcast_notice():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [None, None]  # no existing match, no notice
    with pytest.raises(LookupError):
        register_interest(db, ticket_id=1, hei_id=2)


def test_register_interest_is_idempotent_when_already_registered():
    db = MagicMock()
    existing = MagicMock(status="accepted")
    db.query.return_value.filter.return_value.one_or_none.return_value = existing
    result = register_interest(db, ticket_id=1, hei_id=2)
    assert result["created"] is False
    assert result["match"] is existing


def test_register_interest_rejects_if_previously_declined():
    db = MagicMock()
    existing = MagicMock(status="declined")
    db.query.return_value.filter.return_value.one_or_none.return_value = existing
    with pytest.raises(ValueError, match="declined"):
        register_interest(db, ticket_id=1, hei_id=2)


def test_register_interest_rejects_when_no_capacity_or_capability():
    db = MagicMock()
    notice = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [None, notice]
    with patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "_best_capability_for_hei", return_value=None):
        with pytest.raises(ValueError, match="capacity"):
            register_interest(db, ticket_id=1, hei_id=2)


def test_register_interest_creates_an_accepted_match_directly():
    """Self-initiated join skips 'proposed' - the HEI is telling us it
    wants in, not asking us to decide for it."""
    db = MagicMock()
    notice = MagicMock()
    best = {"hei_id": 2, "capability_id": 9, "institution_name": "NIT Jamshedpur", "contact_email": "x@nitjsr.ac.in", "similarity": 0.6}
    db.query.return_value.filter.return_value.one_or_none.side_effect = [None, notice]

    with patch.object(matcher_module, "load_ticket_for_match", return_value=_ticket()), \
         patch.object(matcher_module, "_best_capability_for_hei", return_value=best):
        result = register_interest(db, ticket_id=1, hei_id=2)

    assert result["created"] is True
    assert result["match"].status == "accepted"
    assert result["match"].hei_id == 2
    assert db.commit.called
