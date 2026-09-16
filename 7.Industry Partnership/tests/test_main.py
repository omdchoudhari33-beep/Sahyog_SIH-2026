from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_ledgers_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/partnership/ledgers")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_release_ledger_funds_json_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post(
            "/partnership/ledgers/1/release", json={"amount": "100", "released_by": "x"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_release_ledger_funds_json_shares_release_funds_with_admin_form(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    from unittest.mock import patch
    fake_release = MagicMock(id=1, amount_released="100.00")
    with patch("app.main.release_funds", return_value=fake_release) as mock_release:
        try:
            response = TestClient(app).post(
                "/partnership/ledgers/1/release",
                headers={"X-Internal-Token": "expected-secret"},
                json={"amount": "100", "released_by": "x", "milestone_id": None},
            )
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_release.assert_called_once()


def test_partnership_route_rejects_missing_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post("/partnership/proposal-approved/1")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_partnership_reconcile_registered_before_id_route(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.reconcile_matches", lambda db: {"scanned": 0, "matched": 0, "proposal_ids": []})
    try:
        response = TestClient(app).post("/partnership/reconcile", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["scanned"] == 0


def test_partner_page_does_not_require_internal_token():
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    fake_db.query.return_value.filter.return_value.one_or_none.return_value = None
    try:
        response = TestClient(app).get("/partner/some-token")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404  # not 401


def test_admin_onboard_partner_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).get("/admin/onboard-partner")
    assert response.status_code == 401


def test_admin_onboard_partner_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).get("/admin/onboard-partner", auth=("admin", "secret123"))
    assert response.status_code == 200


def test_admin_ledger_release_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    response = TestClient(app).post("/admin/ledger/1/release", data={"amount": "100", "released_by": "x"})
    assert response.status_code == 401
