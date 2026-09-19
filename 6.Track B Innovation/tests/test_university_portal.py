import io
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import _location_cell, _problem_cell, _upload_solution_document, app


def test_university_login_form_loads():
    response = TestClient(app).get("/university/login")
    assert response.status_code == 200
    assert "Registered email" in response.text


def test_university_login_rejects_bad_credentials():
    from app.auth import InvalidCredentialsError

    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    with patch("app.main.auth_login", side_effect=InvalidCredentialsError()):
        try:
            response = TestClient(app).post(
                "/university/login", data={"email": "x@example.com", "password": "wrong"}
            )
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 401
    assert "Invalid email or password" in response.text


def test_university_login_success_sets_session_cookie():
    fake_db = MagicMock()
    hei = MagicMock(id=1)
    app.dependency_overrides[get_db] = lambda: fake_db
    with patch("app.main.auth_login", return_value=(hei, "real-session-token")):
        try:
            response = TestClient(app).post(
                "/university/login", data={"email": "x@example.com", "password": "correct"},
                follow_redirects=False,
            )
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 303
    assert response.cookies.get("hei_session") == "real-session-token"


def test_university_dashboard_requires_login():
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/university/dashboard")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_university_dashboard_loads_for_valid_session():
    fake_db = MagicMock()
    hei = MagicMock(id=1, institution_name="Demo Institute", contact_email="hei@example.com")
    fake_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    app.dependency_overrides[get_db] = lambda: fake_db
    with patch("app.main.resolve_session", return_value=hei):
        try:
            response = TestClient(app).get("/university/dashboard", cookies={"hei_session": "valid-token"})
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Demo Institute" in response.text


def test_university_decide_rejects_match_not_owned_by_this_hei():
    """A logged-in HEI must not be able to act on another HEI's match by
    guessing its match_id - ownership is checked, not just session validity."""
    fake_db = MagicMock()
    hei = MagicMock(id=1)
    other_hei_match = MagicMock(id=99, hei_id=2)  # belongs to a different HEI
    fake_db.query.return_value.filter.return_value.one_or_none.return_value = other_hei_match
    app.dependency_overrides[get_db] = lambda: fake_db
    with patch("app.main.resolve_session", return_value=hei):
        try:
            response = TestClient(app).post(
                "/university/matches/99/decide", data={"decision": "accept"},
                cookies={"hei_session": "valid-token"},
            )
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 404


def test_trackb_proposals_pending_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).get("/trackb/proposals/pending")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_nodal_decision_json_requires_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        response = TestClient(app).post(
            "/trackb/proposals/1/nodal-decision",
            json={"decision": "approved", "nodal_officer_id": "x"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_nodal_decision_json_accepts_correct_token_and_shares_nodal_decide(monkeypatch):
    """The JSON entry point must call the SAME nodal_decide() the HTML form
    uses, not a re-implementation - this is what keeps the two Approve
    flows (Admin Portal proxy vs direct HTML form) from drifting apart."""
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "expected-secret")
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    fake_proposal = MagicMock(
        id=1, team_id=1, ticket_id=1, title="T", summary="S", requested_budget=None,
        timeline_weeks=None, status="approved", nodal_officer_id="x", nodal_notes=None,
        solution_document_media_id=None, solution_document_url=None,
        submitted_at="2026-09-16T00:00:00Z", decided_at="2026-09-16T00:00:00Z",
    )
    with patch("app.main.nodal_decide", return_value=fake_proposal) as mock_decide:
        try:
            response = TestClient(app).post(
                "/trackb/proposals/1/nodal-decision",
                headers={"X-Internal-Token": "expected-secret"},
                json={"decision": "approved", "nodal_officer_id": "x", "notes": "ok"},
            )
        finally:
            app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_decide.assert_called_once_with(fake_db, 1, "approved", "x", "ok")


def test_problem_cell_shows_statement_and_photo():
    info = {
        "standardized_problem_statement": "Pothole near the market",
        "domain": "ROADS_BRIDGES", "photo_bucket": "sahyog-images", "photo_object_key": "x.jpg",
    }
    html = _problem_cell(info)
    assert "Pothole near the market" in html
    assert "Roads Bridges" in html
    assert "<img" in html


def test_problem_cell_handles_missing_ticket_info():
    assert "—" in _problem_cell(None)


def test_location_cell_falls_back_to_coordinates_when_geocoding_fails(monkeypatch):
    monkeypatch.setattr("app.main.reverse_geocode", lambda lat, lon: None)
    html = _location_cell({"latitude": 23.34, "longitude": 85.31})
    assert "23.34000" in html
    assert "google.com/maps" in html


def test_location_cell_uses_resolved_place_name(monkeypatch):
    monkeypatch.setattr("app.main.reverse_geocode", lambda lat, lon: "Kanke, Ranchi, Jharkhand")
    html = _location_cell({"latitude": 23.34, "longitude": 85.31})
    assert "Kanke, Ranchi, Jharkhand" in html


def test_location_cell_handles_missing_coordinates():
    assert "Not available" in _location_cell({"latitude": None, "longitude": None})


def test_upload_solution_document_returns_none_when_no_file():
    assert _upload_solution_document(None) is None


def test_upload_solution_document_stores_pdf_and_returns_media_id():
    fake_file = MagicMock()
    fake_file.filename = "solution.pdf"
    fake_file.content_type = "application/pdf"
    fake_file.file = io.BytesIO(b"%PDF-1.4 fake pdf bytes")

    with patch("app.main.storage") as mock_storage:
        mock_storage.build_object_key.return_value = "proposal-solutions/2026/09/18/abc.pdf"
        mock_storage.upload.return_value = MagicMock(media_id=42)
        media_id = _upload_solution_document(fake_file)

    assert media_id == 42
    mock_storage.upload.assert_called_once()


def test_upload_solution_document_fails_soft_on_storage_error():
    fake_file = MagicMock()
    fake_file.filename = "solution.pdf"
    fake_file.file = io.BytesIO(b"data")
    with patch("app.main.storage") as mock_storage:
        mock_storage.upload.side_effect = Exception("MinIO unreachable")
        assert _upload_solution_document(fake_file) is None
