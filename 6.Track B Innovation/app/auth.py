"""University Portal authentication: password hashing (PBKDF2-HMAC-SHA256,
stdlib only, no new dependency) + server-side sessions for HEI logins.

This is a real login system, not a shared secret - each HEI gets its own
credentials. Session tokens follow the same server-side, revocable-by-row
pattern as every other token table in this repo (hei_matches.match_token,
5.ULB Dispatch's status_link_tokens), rather than a signed cookie/JWT that
can't be revoked without a blocklist.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db import HeiRegistry, HeiSession

_PBKDF2_ITERATIONS = 600_000  # OWASP 2023 minimum recommendation for PBKDF2-HMAC-SHA256
_SESSION_TTL_HOURS = 24 * 30  # 30 days - a returning-user portal, not a one-off link


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


class InvalidCredentialsError(Exception):
    pass


class SessionExpiredError(Exception):
    pass


def login(db: Session, email: str, password: str) -> tuple[HeiRegistry, str]:
    hei = db.query(HeiRegistry).filter(HeiRegistry.contact_email == email, HeiRegistry.active.is_(True)).one_or_none()
    if hei is None or not hei.password_hash or not verify_password(password, hei.password_hash):
        # Deliberately the same error for "no such HEI" and "wrong password" -
        # do not leak which registered emails exist.
        raise InvalidCredentialsError("invalid email or password")

    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_SESSION_TTL_HOURS)
    db.add(HeiSession(hei_id=hei.id, session_token=session_token, expires_at=expires_at))
    db.commit()
    return hei, session_token


def resolve_session(db: Session, session_token: str) -> HeiRegistry:
    session = db.query(HeiSession).filter(HeiSession.session_token == session_token).one_or_none()
    if session is None:
        raise SessionExpiredError("no such session")
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise SessionExpiredError("session has expired")

    hei = db.query(HeiRegistry).filter(HeiRegistry.id == session.hei_id, HeiRegistry.active.is_(True)).one_or_none()
    if hei is None:
        raise SessionExpiredError("HEI account no longer active")
    return hei


def logout(db: Session, session_token: str) -> None:
    db.query(HeiSession).filter(HeiSession.session_token == session_token).delete()
    db.commit()
