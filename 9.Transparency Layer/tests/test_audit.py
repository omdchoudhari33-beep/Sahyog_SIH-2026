from unittest.mock import MagicMock

from app.audit import get_entries_for_entity, log_event


def test_log_event_creates_and_commits_entry():
    db = MagicMock()
    entry = log_event(db, service_name="6.Track B Innovation", entity_type="ticket", entity_id=1, event="matched", actor="system", payload={"hei_id": 1})
    assert entry.service_name == "6.Track B Innovation"
    assert entry.entity_type == "ticket"
    assert entry.event == "matched"
    assert db.commit.called


def test_get_entries_for_entity_orders_by_occurred_at():
    db = MagicMock()
    fake_entries = [MagicMock(), MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_entries
    result = get_entries_for_entity(db, entity_type="ticket", entity_id=1)
    assert result == fake_entries
