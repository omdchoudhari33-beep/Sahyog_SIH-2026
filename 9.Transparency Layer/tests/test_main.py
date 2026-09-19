from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_audit_log_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post("/audit/log", json={"service_name": "x", "entity_type": "ticket", "entity_id": 1, "event": "sent"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_audit_log_accepts_correct_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    saved = MagicMock(id=1, service_name="x", entity_type="ticket", entity_id=1, event="sent", actor=None, payload=None, occurred_at="2026-09-16T00:00:00Z")
    monkeypatch.setattr("app.main.log_event", lambda *a, **k: saved)
    try:
        response = TestClient(app).post(
            "/audit/log", headers={"X-Internal-Token": "expected-secret"},
            json={"service_name": "x", "entity_type": "ticket", "entity_id": 1, "event": "sent"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


def test_dashboard_does_not_require_internal_token(monkeypatch):
    """X1/X2 are intentionally public read-only views - only POST /audit/log
    is gated."""
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.full_dashboard", lambda db: {
        "district_domain_heatmap": [], "hei_participation": {"active_heis": 0, "pending_matches": 0, "declined_matches": 0},
        "industry_engagement": {"active_partners": 0, "pending_matches": 0, "total_committed_amount": 0},
        "completion_rate": {"pilots_passed": 0, "pilots_failed": 0, "pilots_pending": 0},
        "outcomes": {"handovers": 0, "spinouts": 0, "track_a_resolved": 0, "patents_filed": 0, "patents_granted": 0},
    })
    try:
        response = TestClient(app).get("/transparency/dashboard")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


def test_status_json_route_registered_before_id_route(monkeypatch):
    """Path-shadowing check: /status/{id}.json must not be swallowed by
    /status/{ticket_id} (same class of bug as 5.ULB Dispatch's
    /dispatch/reconcile lesson)."""
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.get_unified_status", lambda db, ticket_id: {"ticket_id": ticket_id, "domain": "ROADS_BRIDGES", "status": "active", "problem_statement": "x", "track": None, "track_a": None, "track_b": None})
    try:
        response = TestClient(app).get("/status/13.json")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["ticket_id"] == 13


def test_status_page_returns_404_for_missing_ticket(monkeypatch):
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.get_unified_status", lambda db, ticket_id: None)
    try:
        response = TestClient(app).get("/status/999")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
