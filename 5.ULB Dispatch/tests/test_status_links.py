from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.status_links import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    mark_token_used,
    resolve_status_token,
)


def _make_db(token):
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = token
    return db


def test_resolve_status_token_raises_lookup_error_when_missing():
    db = _make_db(None)
    with pytest.raises(LookupError):
        resolve_status_token(db, "does-not-exist")


def test_resolve_status_token_raises_when_expired():
    token = MagicMock(expires_at=datetime.now(timezone.utc) - timedelta(hours=1), used_at=None)
    db = _make_db(token)
    with pytest.raises(TokenExpiredError):
        resolve_status_token(db, "expired-token")


def test_resolve_status_token_raises_when_already_used():
    token = MagicMock(
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used_at=datetime.now(timezone.utc),
    )
    db = _make_db(token)
    with pytest.raises(TokenAlreadyUsedError):
        resolve_status_token(db, "used-token")


def test_resolve_status_token_succeeds_when_valid():
    token = MagicMock(expires_at=datetime.now(timezone.utc) + timedelta(hours=1), used_at=None)
    db = _make_db(token)
    result = resolve_status_token(db, "valid-token")
    assert result is token


def test_mark_token_used_sets_used_at():
    token = MagicMock(used_at=None)
    db = MagicMock()
    mark_token_used(db, token)
    assert token.used_at is not None
