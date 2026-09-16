from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.db import StatusLinkToken


def create_status_link(db: Session, dispatch_id: int) -> tuple[StatusLinkToken, str]:
    token_value = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.STATUS_LINK_TOKEN_TTL_HOURS)
    token = StatusLinkToken(dispatch_id=dispatch_id, token=token_value, expires_at=expires_at)
    db.add(token)
    db.flush()
    url = f"{settings.STATUS_LINK_BASE_URL.rstrip('/')}/status/{token_value}"
    return token, url


class TokenExpiredError(Exception):
    pass


class TokenAlreadyUsedError(Exception):
    pass


def resolve_status_token(db: Session, token_value: str) -> StatusLinkToken:
    token = db.query(StatusLinkToken).filter(StatusLinkToken.token == token_value).one_or_none()
    if token is None:
        raise LookupError("status link token not found")
    now = datetime.now(timezone.utc)
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise TokenExpiredError("status link token has expired")
    if token.used_at is not None:
        raise TokenAlreadyUsedError("status link token has already been used")
    return token


def mark_token_used(db: Session, token: StatusLinkToken) -> None:
    token.used_at = datetime.now(timezone.utc)
    db.add(token)
    db.flush()
