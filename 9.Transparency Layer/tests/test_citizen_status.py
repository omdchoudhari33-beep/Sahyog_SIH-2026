from unittest.mock import MagicMock

from app.citizen_status import get_unified_status


def test_get_unified_status_returns_none_when_ticket_missing():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.one_or_none.return_value = None
    result = get_unified_status(db, ticket_id=999)
    assert result is None


def test_get_unified_status_returns_base_fields_when_no_decision_yet():
    db = MagicMock()
    ticket_row = {"id": 1, "domain": "ROADS_BRIDGES", "status": "active", "standardized_problem_statement": "Pothole", "ai_suggested_track": None}

    call_count = {"n": 0}

    def execute_side_effect(stmt, params=None):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.mappings.return_value.one_or_none.return_value = ticket_row
        else:
            result.mappings.return_value.one_or_none.return_value = None  # no decision yet
        return result

    db.execute.side_effect = execute_side_effect
    result = get_unified_status(db, ticket_id=1)
    assert result["ticket_id"] == 1
    assert result["track"] is None
    assert result["track_a"] is None


def test_get_unified_status_decision_query_uses_created_at_not_decided_at():
    """Regression test for a real bug caught in live testing:
    validation_decisions has a created_at column, not decided_at - an
    earlier draft's SQL referenced a column that doesn't exist and 500'd
    on every ticket that had a recorded decision."""
    db = MagicMock()
    ticket_row = {"id": 1, "domain": "ROADS_BRIDGES", "status": "active", "standardized_problem_statement": "Pothole", "ai_suggested_track": None}

    call_count = {"n": 0}
    captured_sql = {}

    def execute_side_effect(stmt, params=None):
        call_count["n"] += 1
        if call_count["n"] == 2:
            captured_sql["decision_query"] = str(stmt)
        result = MagicMock()
        result.mappings.return_value.one_or_none.return_value = ticket_row if call_count["n"] == 1 else None
        return result

    db.execute.side_effect = execute_side_effect
    get_unified_status(db, ticket_id=1)
    assert "created_at" in captured_sql["decision_query"]
    assert "decided_at" not in captured_sql["decision_query"].split("AS")[0]  # decided_at only appears as an alias, not a real column reference


def test_get_unified_status_track_a_includes_dispatch():
    db = MagicMock()
    ticket_row = {"id": 1, "domain": "ROADS_BRIDGES", "status": "validated", "standardized_problem_statement": "Pothole", "ai_suggested_track": "track_a"}
    decision_row = {"decision": "track_a", "decided_at": "2026-09-16"}
    dispatch_row = {"status": "sent", "correlation_code": "SAHYOG-1-ABCDEF", "sent_at": "2026-09-16"}

    call_count = {"n": 0}

    def execute_side_effect(stmt, params=None):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.mappings.return_value.one_or_none.return_value = ticket_row
        elif call_count["n"] == 2:
            result.mappings.return_value.one_or_none.return_value = decision_row
        else:
            result.mappings.return_value.one_or_none.return_value = dispatch_row
        return result

    db.execute.side_effect = execute_side_effect
    result = get_unified_status(db, ticket_id=1)
    assert result["track"] == "track_a"
    assert result["track_a"]["correlation_code"] == "SAHYOG-1-ABCDEF"
