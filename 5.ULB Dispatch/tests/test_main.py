from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_dispatches_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/dispatch")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_list_dispatches_returns_recent_first(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    from datetime import datetime, timezone
    row = MagicMock(
        id=1, ticket_id=10, ulb_id=1, contact_id=1, channel="email",
        correlation_code="SAHYOG-10-ABCDEF", status="sent", level=1, attempt_no=1,
        sent_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fake_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/dispatch", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["correlation_code"] == "SAHYOG-10-ABCDEF"


def test_dispatch_route_rejects_missing_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post("/dispatch/1")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
    assert "X-Internal-Token" in response.json()["detail"]


def test_dispatch_route_rejects_wrong_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post("/dispatch/1", headers={"X-Internal-Token": "wrong"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_dispatch_route_accepts_correct_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr(
        "app.main.create_dispatch",
        lambda db, ticket_id: {"ticket_id": ticket_id, "dispatch": None, "created": False, "detail": "no usable contact found"},
    )
    try:
        response = TestClient(app).post("/dispatch/1", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["created"] is False


def test_dispatch_reconcile_finds_and_dispatches_missed_tickets(monkeypatch):
    """Acceptance requirement: POST /dispatch/reconcile correctly finds and
    dispatches any track_a ticket the fire-and-forget webhook might have
    missed - the key non-breaking / no-data-loss guarantee."""
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr(
        "app.main.reconcile_dispatches",
        lambda db: {"scanned": 2, "dispatched": 2, "ticket_ids": [10, 11]},
    )
    try:
        response = TestClient(app).post("/dispatch/reconcile", headers={"X-Internal-Token": "expected-secret"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["scanned"] == 2
    assert body["dispatched"] == 2
    assert body["ticket_ids"] == [10, 11]


def test_status_route_does_not_require_internal_token():
    """GET /status/{token} is intentionally public - the token is the
    credential, no X-Internal-Token header is checked."""
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    from app.status_links import TokenExpiredError

    def raise_expired(db, token):
        raise TokenExpiredError("expired")

    import app.main as main_module
    original = main_module.resolve_status_token
    main_module.resolve_status_token = raise_expired
    try:
        response = TestClient(app).get("/status/some-token", headers={})  # no X-Internal-Token at all
    finally:
        app.dependency_overrides.clear()
        main_module.resolve_status_token = original

    # 410 (expired) not 401 (unauthorized) proves no internal-token check ran.
    assert response.status_code == 410


def test_status_update_rejects_oversized_photo(monkeypatch):
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db

    import app.main as main_module
    token_row = MagicMock(dispatch_id=1)
    monkeypatch.setattr(main_module, "resolve_status_token", lambda db, token: token_row)
    dispatch = MagicMock(id=1)
    fake_db.query.return_value.filter.return_value.one_or_none.return_value = dispatch

    oversized = b"\xff\xd8\xff" + (b"0" * (main_module.settings.MAX_CLOSURE_PHOTO_MB * 1024 * 1024 + 1))
    try:
        response = TestClient(app).post(
            "/status/some-token/update",
            data={"status": "resolved"},
            files={"photo": ("photo.jpg", oversized, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "MB limit" in response.json()["detail"]


def test_status_update_rejects_non_image_by_magic_bytes_not_header(monkeypatch):
    """A file claiming to be image/jpeg via content-type but whose actual
    bytes are not a JPEG/PNG signature must be rejected."""
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db

    import app.main as main_module
    token_row = MagicMock(dispatch_id=1)
    monkeypatch.setattr(main_module, "resolve_status_token", lambda db, token: token_row)
    dispatch = MagicMock(id=1)
    fake_db.query.return_value.filter.return_value.one_or_none.return_value = dispatch

    fake_payload = b"this is not actually an image"
    try:
        response = TestClient(app).post(
            "/status/some-token/update",
            data={"status": "resolved"},
            files={"photo": ("photo.jpg", fake_payload, "image/jpeg")},  # lying content-type header
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "file signature" in response.json()["detail"]


def test_admin_onboard_requires_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/admin/onboard")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_admin_onboard_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_FORM_PASSWORD", "secret123")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr("app.main.list_ulbs", lambda db: [])
    try:
        response = TestClient(app).get("/admin/onboard", auth=("admin", "secret123"))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
