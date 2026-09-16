from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.auth import (
    InvalidCredentialsError,
    SessionExpiredError,
    hash_password,
    login,
    logout,
    resolve_session,
    verify_password,
)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_password_rejects_garbage_hash():
    assert verify_password("anything", "not-a-real-hash") is False


def test_hash_password_uses_a_random_salt_each_time():
    """Two hashes of the same password must differ (different salt) - a
    fixed/no salt would make identical passwords produce identical hashes,
    letting an attacker with DB read access spot password reuse."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_login_raises_on_unknown_email():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(InvalidCredentialsError):
        login(db, "nobody@example.com", "whatever")


def test_login_raises_on_wrong_password():
    db = MagicMock()
    hei = MagicMock(password_hash=hash_password("correct-password"))
    db.query.return_value.filter.return_value.one_or_none.return_value = hei
    with pytest.raises(InvalidCredentialsError):
        login(db, "hei@example.com", "wrong-password")


def test_login_succeeds_and_creates_a_session():
    db = MagicMock()
    hei = MagicMock(id=1, password_hash=hash_password("correct-password"))
    db.query.return_value.filter.return_value.one_or_none.return_value = hei
    result_hei, token = login(db, "hei@example.com", "correct-password")
    assert result_hei is hei
    assert token
    assert db.add.called
    assert db.commit.called


def test_resolve_session_raises_when_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(SessionExpiredError):
        resolve_session(db, "no-such-token")


def test_resolve_session_raises_when_expired():
    db = MagicMock()
    session = MagicMock(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))

    def query_side_effect(model):
        m = MagicMock()
        if model.__name__ == "HeiSession":
            m.filter.return_value.one_or_none.return_value = session
        return m

    db.query.side_effect = query_side_effect
    with pytest.raises(SessionExpiredError):
        resolve_session(db, "expired-token")


def test_resolve_session_succeeds_for_valid_session():
    db = MagicMock()
    session = MagicMock(hei_id=1, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    hei = MagicMock(id=1)

    def query_side_effect(model):
        m = MagicMock()
        if model.__name__ == "HeiSession":
            m.filter.return_value.one_or_none.return_value = session
        else:
            m.filter.return_value.one_or_none.return_value = hei
        return m

    db.query.side_effect = query_side_effect
    result = resolve_session(db, "valid-token")
    assert result is hei


def test_logout_deletes_the_session():
    db = MagicMock()
    logout(db, "some-token")
    assert db.query.return_value.filter.return_value.delete.called
    assert db.commit.called
