from unittest.mock import MagicMock, patch

import pytest

from app.disposition import apply_disposition


def test_apply_disposition_rejects_invalid_value():
    db = MagicMock()
    with pytest.raises(ValueError):
        apply_disposition(db, ticket_id=1, proposal_id=1, disposition="bogus", notes=None, startup_name=None, incubator_name=None)


def test_apply_disposition_spinout_requires_startup_name():
    db = MagicMock()
    with pytest.raises(ValueError, match="startup_name"):
        apply_disposition(db, ticket_id=1, proposal_id=1, disposition="spinout", notes=None, startup_name=None, incubator_name=None)


def test_apply_disposition_handover_calls_record_handover():
    db = MagicMock()
    with patch("app.disposition.record_handover", return_value=MagicMock(id=1)) as mock_handover:
        result = apply_disposition(db, ticket_id=1, proposal_id=1, disposition="handover", notes="done", startup_name=None, incubator_name=None)
    mock_handover.assert_called_once_with(db, 1, "done")
    assert result["handover_id"] == 1


def test_apply_disposition_spinout_calls_record_spinout():
    db = MagicMock()
    with patch("app.disposition.record_spinout", return_value=MagicMock(id=2)) as mock_spinout:
        result = apply_disposition(db, ticket_id=1, proposal_id=1, disposition="spinout", notes=None, startup_name="Acme Fix Co", incubator_name="Demo Incubator")
    mock_spinout.assert_called_once_with(db, 1, "Acme Fix Co", "Demo Incubator", None)
    assert result["spinout_id"] == 2


def test_apply_disposition_both_calls_handover_and_spinout():
    db = MagicMock()
    with patch("app.disposition.record_handover", return_value=MagicMock(id=1)), \
         patch("app.disposition.record_spinout", return_value=MagicMock(id=2)):
        result = apply_disposition(db, ticket_id=1, proposal_id=1, disposition="both", notes=None, startup_name="Acme Fix Co", incubator_name=None)
    assert result["handover_id"] == 1
    assert result["spinout_id"] == 2


def test_record_handover_never_raises_when_ulb_dispatch_unreachable():
    import httpx as _httpx
    db = MagicMock()
    from app.disposition import record_handover
    with patch("app.disposition.httpx.post", side_effect=_httpx.ConnectError("refused")):
        record = record_handover(db, ticket_id=1, notes="notes")
    assert record.ulb_dispatch_id is None
    assert db.commit.called
