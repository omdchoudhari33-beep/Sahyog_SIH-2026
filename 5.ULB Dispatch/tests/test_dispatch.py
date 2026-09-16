from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app import dispatch as dispatch_module
from app.dispatch import (
    TicketForDispatch,
    _insert_dispatch_row,
    consecutive_api_errors,
    create_dispatch,
    get_active_dispatch,
    pick_contact,
)


def _ticket():
    return TicketForDispatch(
        id=1, domain="ROADS_BRIDGES", standardized_problem_statement="Pothole on Main St",
        severity=3.0, population_impact=2.0, lat=23.3, lon=85.3,
    )


def test_create_dispatch_is_idempotent_when_active_dispatch_exists():
    db = MagicMock()
    existing = MagicMock(id=5, status="sent")
    with patch.object(dispatch_module, "get_active_dispatch", return_value=existing):
        result = create_dispatch(db, ticket_id=1)
    assert result["created"] is False
    assert result["dispatch"] is existing


def test_insert_dispatch_row_retries_on_correlation_code_collision():
    db = MagicMock()
    contact = MagicMock(ulb_id=1, id=10)
    ticket = _ticket()

    calls = {"n": 0}

    def flush_side_effect():
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("insert", {}, Exception("duplicate key value violates unique constraint \"dispatches_correlation_code_key\""))
        return None

    db.flush.side_effect = flush_side_effect

    dispatch = _insert_dispatch_row(db, ticket, contact, "email", level=1, attempt_no=1)
    assert dispatch is not None
    assert db.rollback.called


def test_insert_dispatch_row_returns_existing_on_ticket_uniqueness_collision():
    db = MagicMock()
    contact = MagicMock(ulb_id=1, id=10)
    ticket = _ticket()
    existing = MagicMock(id=42, status="sent")

    db.flush.side_effect = IntegrityError(
        "insert", {}, Exception("duplicate key value violates unique constraint \"uq_dispatches_ticket_active\"")
    )

    with patch.object(dispatch_module, "get_active_dispatch", return_value=existing):
        result = _insert_dispatch_row(db, ticket, contact, "email", level=1, attempt_no=1)

    assert result is existing


def test_consecutive_api_errors_stops_at_first_non_error():
    db = MagicMock()
    rows = [
        {"event_type": "api_error"},
        {"event_type": "api_error"},
        {"event_type": "sent"},
        {"event_type": "api_error"},
    ]
    db.execute.return_value.mappings.return_value.all.return_value = rows
    assert consecutive_api_errors(db, contact_id=1) == 2


def test_pick_contact_demotes_api_after_three_consecutive_failures():
    db = MagicMock()
    api_contact = MagicMock(id=1, channel="api")
    email_contact = MagicMock(id=2, channel="email")

    with patch.object(dispatch_module, "resolve_contacts", return_value=[api_contact, email_contact]), \
         patch.object(dispatch_module, "consecutive_api_errors", return_value=3):
        chosen = pick_contact(db, ticket_id=1, level=1, preferred_channel="api")

    assert chosen is email_contact


def test_pick_contact_prefers_api_when_healthy():
    db = MagicMock()
    api_contact = MagicMock(id=1, channel="api")
    email_contact = MagicMock(id=2, channel="email")

    with patch.object(dispatch_module, "resolve_contacts", return_value=[api_contact, email_contact]), \
         patch.object(dispatch_module, "consecutive_api_errors", return_value=0):
        chosen = pick_contact(db, ticket_id=1, level=1, preferred_channel="api")

    assert chosen is api_contact
