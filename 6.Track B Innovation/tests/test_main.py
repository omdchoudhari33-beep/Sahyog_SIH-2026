from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_trackb_route_rejects_missing_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post("/trackb/1")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_trackb_route_accepts_correct_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr(
        "app.main.create_match",
        lambda db, ticket_id: {"ticket_id": ticket_id, "match": None, "created": False, "detail": "no HEI capability match found"},
    )
    try:
        response = TestClient(app).post("/trackb/1", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["created"] is False


def test_trackb_reconcile_registered_before_ticket_id_route(monkeypatch):
    """Path-shadowing check: /trackb/reconcile must not be swallowed by
    /trackb/{ticket_id} (learned the hard way building 5.ULB Dispatch)."""
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.reconcile_matches", lambda db: {"scanned": 0, "matched": 0, "ticket_ids": []})
    try:
        response = TestClient(app).post("/trackb/reconcile", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["scanned"] == 0


def test_hei_page_does_not_require_internal_token():
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    fake_db.query.return_value.filter.return_value.one_or_none.return_value = None
    try:
        response = TestClient(app).get("/hei/some-token")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404  # not 401 - proves no internal-token check ran


def test_admin_onboard_hei_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).get("/admin/onboard-hei")
    assert response.status_code == 401


def test_admin_onboard_hei_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).get("/admin/onboard-hei", auth=("admin", "secret123"))
    assert response.status_code == 200
