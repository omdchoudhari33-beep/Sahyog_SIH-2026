from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.db import get_db
from app.priority import calculate_priority_score
from app.validation import classify_ticket


def test_classification_routes_configured_domains():
    assert classify_ticket(" roads ", "high") == "track_a"
    assert classify_ticket("AGRICULTURAL_DISEASE", "low") == "track_b"
    assert classify_ticket(None, None) == "review_required"


def test_priority_score_uses_configured_weights():
    original = (
        settings.PRIORITY_SEVERITY_WEIGHT,
        settings.PRIORITY_CLUSTER_SIZE_WEIGHT,
        settings.PRIORITY_AGE_HOURS_WEIGHT,
        settings.PRIORITY_POPULATION_IMPACT_WEIGHT,
    )
    try:
        settings.PRIORITY_SEVERITY_WEIGHT = 2.0
        settings.PRIORITY_CLUSTER_SIZE_WEIGHT = 1.0
        settings.PRIORITY_AGE_HOURS_WEIGHT = 0.5
        settings.PRIORITY_POPULATION_IMPACT_WEIGHT = 1.0
        assert calculate_priority_score(5, 3, 10, 20) == 38.0
    finally:
        (
            settings.PRIORITY_SEVERITY_WEIGHT,
            settings.PRIORITY_CLUSTER_SIZE_WEIGHT,
            settings.PRIORITY_AGE_HOURS_WEIGHT,
            settings.PRIORITY_POPULATION_IMPACT_WEIGHT,
        ) = original


def test_health_endpoint_is_available():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dno_queue_returns_suggested_track(monkeypatch):
    fake_db = Mock()
    ticket = {
        "ticket_id": 42,
        "master_ticket_id": None,
        "problem_statement": "Large pothole",
        "domain": "ROADS",
        "urgency": "HIGH",
        "severity": 4.0,
        "population_impact": 3.0,
        "status": "active",
        "cluster_count": 7,
        "priority_score": 12.4,
        "created_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "suggested_track": "track_a",
    }
    monkeypatch.setattr("app.main.list_prioritized_tickets", lambda db, limit, offset: [ticket])
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/dno/tickets?limit=1&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["suggested_track"] == "track_a"


def test_dno_decision_persists_and_returns_result(monkeypatch):
    fake_db = Mock()
    result = {
        "ticket_id": 42,
        "decision": "track_a",
        "status": "validated",
        "operator_id": "operator-1",
        "notes": "Validated road obstruction",
        "decided_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }
    apply = Mock(return_value=result)
    monkeypatch.setattr("app.main.apply_operator_decision", apply)
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post(
            "/dno/tickets/42/decision",
            json={
                "decision": "track_a",
                "operator_id": "operator-1",
                "notes": "Validated road obstruction",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "validated"
    apply.assert_called_once_with(
        fake_db, 42, "track_a", "operator-1", "Validated road obstruction"
    )