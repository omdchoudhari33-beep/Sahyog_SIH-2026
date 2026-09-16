from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pending_dispositions_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/lifecycle/pending-dispositions")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_lifecycle_disposition_json_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post(
            "/lifecycle/1/disposition", json={"proposal_id": 1, "disposition": "handover"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_lifecycle_disposition_json_shares_apply_disposition_with_admin_form(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    from unittest.mock import patch
    with patch("app.main.apply_disposition", return_value={"ticket_id": 1, "proposal_id": 1, "disposition": "handover", "handover_id": 1}) as mock_apply:
        try:
            response = TestClient(app).post(
                "/lifecycle/1/disposition",
                headers={"X-Internal-Token": "expected-secret"},
                json={"proposal_id": 1, "disposition": "handover"},
            )
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_apply.assert_called_once()


def test_lifecycle_route_rejects_missing_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post("/lifecycle/proposal-approved/1")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_lifecycle_reconcile_registered_before_id_route(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.reconcile_milestones", lambda db: {"scanned": 0, "initialized": 0, "proposal_ids": []})
    try:
        response = TestClient(app).post("/lifecycle/reconcile", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["scanned"] == 0


def test_admin_evaluate_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).post("/admin/milestones/1/evaluate", data={"evaluator_name": "x", "score": "0.5"})
    assert response.status_code == 401


def test_admin_disposition_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).post("/admin/1/disposition", data={"proposal_id": "1", "disposition": "handover"})
    assert response.status_code == 401


def test_admin_disposition_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.apply_disposition", lambda *a, **k: {"ticket_id": 1, "proposal_id": 1, "disposition": "handover", "handover_id": 1})
    try:
        response = TestClient(app).post(
            "/admin/1/disposition", auth=("admin", "secret123"),
            data={"proposal_id": "1", "disposition": "handover"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["handover_id"] == 1
