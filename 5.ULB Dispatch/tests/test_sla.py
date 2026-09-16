from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.sla import business_hours_elapsed, scan_overdue

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def test_business_hours_elapsed_uses_ist_not_utc_or_naive():
    """This test would fail if business_hours_elapsed used naive/UTC time
    directly instead of converting to Asia/Kolkata first: a UTC Friday
    18:30 is already Saturday 00:00 IST, so counting from raw UTC would
    (wrongly) include a business day that IST has already finished."""
    # Friday 18:30 UTC == Saturday 00:00 IST (start of the weekend in IST)
    sent_at = datetime(2026, 9, 11, 18, 30, tzinfo=UTC)  # Friday
    # Monday 05:00 UTC == Monday 10:30 IST
    now = datetime(2026, 9, 14, 5, 0, tzinfo=UTC)  # Monday

    elapsed = business_hours_elapsed(sent_at, now)

    # If computed naively off UTC clock times without weekend exclusion in
    # IST, this would be far larger (Sat+Sun would count as business time).
    # In IST: Sat 00:00 -> Mon 00:00 is the full weekend (excluded), then
    # Mon 00:00 -> Mon 10:30 IST = 10.5 business hours.
    assert 10.0 <= elapsed <= 11.0


def test_business_hours_elapsed_excludes_weekend():
    # Saturday 00:00 IST to Monday 00:00 IST should be ~0 business hours.
    sent_at = datetime(2026, 9, 12, 0, 0, tzinfo=IST).astimezone(UTC)  # Saturday IST
    now = datetime(2026, 9, 14, 0, 0, tzinfo=IST).astimezone(UTC)  # Monday IST
    assert business_hours_elapsed(sent_at, now) == pytest.approx(0.0, abs=0.01)


def test_business_hours_elapsed_same_weekday():
    sent_at = datetime(2026, 9, 14, 9, 0, tzinfo=IST).astimezone(UTC)  # Monday 09:00 IST
    now = datetime(2026, 9, 14, 15, 0, tzinfo=IST).astimezone(UTC)  # Monday 15:00 IST
    assert business_hours_elapsed(sent_at, now) == pytest.approx(6.0, abs=0.01)


def test_scan_overdue_escalates_when_sla_exceeded():
    db = MagicMock()
    overdue_dispatch = MagicMock(id=1, ticket_id=100, level=1, status="sent")
    overdue_dispatch.sent_at = datetime.now(UTC) - timedelta(hours=100)

    with patch("app.sla._non_terminal_dispatches", return_value=[overdue_dispatch]), \
         patch("app.sla._sla_hours_for", return_value=48), \
         patch("app.sla._escalate") as mock_escalate:
        db.execute.return_value.mappings.return_value.one_or_none.return_value = {"domain": "ROADS_BRIDGES"}
        count = scan_overdue(db)

    assert count == 1
    mock_escalate.assert_called_once()


def test_scan_overdue_skips_when_within_sla():
    db = MagicMock()
    fresh_dispatch = MagicMock(id=1, ticket_id=100, level=1, status="sent")
    fresh_dispatch.sent_at = datetime.now(UTC) - timedelta(hours=2)

    with patch("app.sla._non_terminal_dispatches", return_value=[fresh_dispatch]), \
         patch("app.sla._sla_hours_for", return_value=48), \
         patch("app.sla._escalate") as mock_escalate:
        db.execute.return_value.mappings.return_value.one_or_none.return_value = {"domain": "ROADS_BRIDGES"}
        count = scan_overdue(db)

    assert count == 0
    mock_escalate.assert_not_called()
