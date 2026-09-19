from unittest.mock import MagicMock, patch

import pytest

from app.closure import haversine_meters, verify_closure


def test_haversine_meters_zero_distance():
    assert haversine_meters(23.3, 85.3, 23.3, 85.3) == pytest.approx(0.0, abs=1e-6)


def test_haversine_meters_known_distance():
    # Roughly 111km per degree of latitude near the equator/mid-latitudes.
    distance = haversine_meters(23.0, 85.0, 24.0, 85.0)
    assert 110_000 <= distance <= 112_000


def _ticket_row(lat=23.3, lon=85.3):
    return {"standardized_problem_statement": "Pothole on Main St", "lat": lat, "lon": lon}


def _make_db(dispatch, ticket_row):
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = dispatch
    db.execute.return_value.mappings.return_value.one_or_none.return_value = ticket_row
    return db


def test_verify_closure_geo_check_passes_and_auto_resolves_for_verified_officer():
    dispatch = MagicMock(id=1, ticket_id=100, status="sent")
    db = _make_db(dispatch, _ticket_row(lat=23.3, lon=85.3))

    with patch("app.closure._get_vision_similarity", return_value=None):
        proof = verify_closure(
            db, dispatch_id=1, photo_bytes=b"fake",
            photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None,
            photo_lat=23.3001, photo_lon=85.3001,  # a few meters away
            exif_captured_at=None, submitted_by="officer",
        )

    assert proof.geo_check_passed is True
    assert proof.verified_at is not None
    assert dispatch.status == "resolved"


def test_verify_closure_geo_check_fails_and_flags_disputed():
    dispatch = MagicMock(id=1, ticket_id=100, status="sent")
    db = _make_db(dispatch, _ticket_row(lat=23.3, lon=85.3))

    with patch("app.closure._get_vision_similarity", return_value=None):
        proof = verify_closure(
            db, dispatch_id=1, photo_bytes=b"fake",
            photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None,
            photo_lat=25.0, photo_lon=90.0,  # far away
            exif_captured_at=None, submitted_by="officer",
        )

    assert proof.geo_check_passed is False
    assert proof.verified_at is None
    assert dispatch.status != "resolved"


def test_verify_closure_citizen_submission_never_auto_resolves():
    dispatch = MagicMock(id=1, ticket_id=100, status="sent")
    db = _make_db(dispatch, _ticket_row(lat=23.3, lon=85.3))

    with patch("app.closure._get_vision_similarity", return_value=None):
        proof = verify_closure(
            db, dispatch_id=1, photo_bytes=b"fake",
            photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None,
            photo_lat=23.3001, photo_lon=85.3001,
            exif_captured_at=None, submitted_by="citizen",
        )

    assert proof.verified_at is None
    assert dispatch.status != "resolved"


def test_verify_closure_always_inserts_a_proof_row_regardless_of_outcome():
    dispatch = MagicMock(id=1, ticket_id=100, status="sent")
    db = _make_db(dispatch, _ticket_row(lat=23.3, lon=85.3))

    with patch("app.closure._get_vision_similarity", return_value=None):
        verify_closure(
            db, dispatch_id=1, photo_bytes=b"fake",
            photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None,
            photo_lat=25.0, photo_lon=90.0,
            exif_captured_at=None, submitted_by="citizen",
        )

    assert db.add.called
    assert db.commit.called
