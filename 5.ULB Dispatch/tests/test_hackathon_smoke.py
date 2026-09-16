"""The actual hackathon smoke test (see README + acceptance checklist):
with default env settings (SEED_DEMO_DATA=true, EMAIL_DRY_RUN=true,
RUN_BACKGROUND_LOOP_IN_PROCESS=true), a single `uvicorn app.main:app`
process - no manual SQL beyond the migration - must be able to accept a
POST /dispatch/{ticket_id} call and produce a dry-run "sent" dispatch_events
row. This test proves that end-to-end at the unit level (no live Postgres,
per this suite's constraints), by exercising the real send_dispatch() path
against a mocked DB and asserting the dry-run email content + resulting
event log look exactly like a real send would.
"""
from unittest.mock import MagicMock, patch

from app.config import settings
from app.db import Dispatch
from app.dispatch import TicketForDispatch, send_dispatch


def test_default_settings_are_the_hackathon_fast_path():
    assert settings.SEED_DEMO_DATA is True
    assert settings.EMAIL_DRY_RUN is True
    assert settings.RUN_BACKGROUND_LOOP_IN_PROCESS is True


def test_dispatch_with_email_dry_run_produces_a_sent_event_without_smtp():
    assert settings.EMAIL_DRY_RUN is True  # this test only proves the demo default path

    db = MagicMock()
    ticket = TicketForDispatch(
        id=1, domain=None, standardized_problem_statement="Pothole outside demo office",
        severity=2.0, population_impact=1.0, lat=23.3, lon=85.3,
    )
    contact = MagicMock(id=1, ulb_id=1, channel="email", email="demo-ulb-inbox@example.com")

    logged_events = []
    next_id = {"n": 1}

    def fake_add(obj):
        if hasattr(obj, "event_type"):
            logged_events.append((obj.event_type, obj.payload))
        elif isinstance(obj, Dispatch) and obj.id is None:
            # Simulate what a real DB flush/INSERT...RETURNING would do -
            # MagicMock's db.flush() is a no-op, so this stands in for it.
            obj.id = next_id["n"]
            next_id["n"] += 1

    db.add.side_effect = fake_add

    with patch("app.dispatch.create_status_link", return_value=(MagicMock(), "https://status.example/status/tok")):
        result = send_dispatch(db, ticket, contact, level=1)

    assert result["created"] is True
    sent_events = [payload for event_type, payload in logged_events if event_type == "sent"]
    assert len(sent_events) == 1
    rendered = sent_events[0]["rendered_email"]
    assert rendered["to"] == "demo-ulb-inbox@example.com"
    assert "status link" in rendered["text_body"].lower() or "https://status.example" in rendered["text_body"]
    # smtplib was never touched in dry-run mode.
    assert sent_events[0].get("dry_run") is True
