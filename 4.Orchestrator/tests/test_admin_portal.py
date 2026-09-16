from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_dashboard_requires_admin_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).get("/dashboard")
    assert response.status_code == 401


def test_dashboard_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).get("/dashboard", auth=("admin", "secret123"))
    assert response.status_code == 200


def test_admin_portal_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).get("/admin")
    assert response.status_code == 401


def test_admin_portal_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).get("/admin", auth=("admin", "secret123"))
    assert response.status_code == 200


def test_api_tickets_now_requires_admin_password(monkeypatch):
    """Regression guard: /api/tickets was unauthenticated before the Admin
    Portal existed - this closes that gap, and this test pins it closed."""
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).get("/api/tickets")
    assert response.status_code == 401


def test_api_admin_track_a_proxies_with_correct_auth(monkeypatch):
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    with patch("app.main.list_track_a_dispatches", new=AsyncMock(return_value=[{"ticket_id": 1}])):
        response = TestClient(app).get("/api/admin/track-a", auth=("admin", "secret123"))
    assert response.status_code == 200
    assert response.json() == [{"ticket_id": 1}]


def test_api_admin_track_b_decide_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).post(
        "/api/admin/track-b/1/decide", json={"decision": "approved", "nodal_officer_id": "x"}
    )
    assert response.status_code == 401


def test_citizen_form_does_not_require_admin_password(monkeypatch):
    """The citizen-facing routes must stay public - only /dashboard and
    /admin (and their /api/* proxies) are gated."""
    monkeypatch.setattr(settings, "admin_portal_password", "secret123")
    response = TestClient(app).get("/")
    assert response.status_code == 200
