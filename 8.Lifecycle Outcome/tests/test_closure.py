from unittest.mock import MagicMock, patch

import pytest

from app.closure import haversine_meters, verify_pilot


def test_haversine_meters_zero_distance():
    assert haversine_meters(23.3, 85.3, 23.3, 85.3) == pytest.approx(0.0, abs=1e-6)


def test_haversine_meters_known_distance():
    distance = haversine_meters(23.0, 85.0, 24.0, 85.0)
    assert 110_000 <= distance <= 112_000


def _ticket_row(lat=23.3, lon=85.3):
    return {"standardized_problem_statement": "Bridge approach collapse", "lat": lat, "lon": lon}


def _make_db(ticket_row):
    db = MagicMock()
    db.execute.return_value.mappings.return_value.one_or_none.return_value = ticket_row
    return db


def test_verify_pilot_passes_when_geo_check_passes_and_vision_skipped():
    db = _make_db(_ticket_row())
    with patch("app.closure._get_vision_similarity", return_value=None):
        result = verify_pilot(db, ticket_id=1, proposal_id=1, photo_bytes=b"fake", photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None, photo_lat=23.3001, photo_lon=85.3001)
    assert result.geo_check_passed is True
    assert result.verdict == "pass"
    assert db.commit.called


def test_verify_pilot_fails_when_geo_check_fails():
    db = _make_db(_ticket_row())
    with patch("app.closure._get_vision_similarity", return_value=None):
        result = verify_pilot(db, ticket_id=1, proposal_id=1, photo_bytes=b"fake", photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None, photo_lat=25.0, photo_lon=90.0)
    assert result.geo_check_passed is False
    assert result.verdict == "fail"


def test_verify_pilot_pending_review_when_no_coordinates():
    db = _make_db(_ticket_row())
    with patch("app.closure._get_vision_similarity", return_value=None):
        result = verify_pilot(db, ticket_id=1, proposal_id=1, photo_bytes=b"fake", photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None, photo_lat=None, photo_lon=None)
    assert result.geo_check_passed is None
    assert result.verdict == "pending_review"


def test_verify_pilot_raises_when_ticket_missing():
    db = _make_db(None)
    with pytest.raises(LookupError):
        verify_pilot(db, ticket_id=1, proposal_id=1, photo_bytes=b"fake", photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None, photo_lat=23.3, photo_lon=85.3)


def test_verify_pilot_always_commits_regardless_of_outcome():
    db = _make_db(_ticket_row())
    with patch("app.closure._get_vision_similarity", return_value=None):
        verify_pilot(db, ticket_id=1, proposal_id=1, photo_bytes=b"fake", photo_url="http://localhost:9000/sahyog-images/fake.jpg", photo_media_id=None, photo_lat=25.0, photo_lon=90.0)
    assert db.add.called
    assert db.commit.called
