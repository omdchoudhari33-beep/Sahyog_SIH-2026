"""IMAP polling for reply-based fallback: officers who just hit 'reply' on
the dispatch email instead of using the status link.

Deliberately simple for this first version - extracts the correlation code
and logs the raw reply for a human to review. Does NOT attempt to parse
free-text reply intent.

# TODO: route to Evidence Extractor's C1 LLM Structuriser for intent
# classification once this MVP is stable.
"""
from __future__ import annotations

import email
import imaplib
import re
from email.message import Message
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.db import Dispatch, DispatchEvent

CORRELATION_CODE_RE = re.compile(r"\[SAHYOG-\d+-[A-Z0-9]{6}\]")


def extract_correlation_code(subject: str, body: str) -> Optional[str]:
    match = CORRELATION_CODE_RE.search(subject or "")
    if not match:
        match = CORRELATION_CODE_RE.search(body or "")
    if not match:
        return None
    return match.group(0).strip("[]")


def _get_body(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="replace") if payload else ""


def poll_inbox(db: Session) -> int:
    """Connects to IMAP, scans unread mail in IMAP_FOLDER, matches replies
    to dispatches by correlation code, logs a 'replied' dispatch_event for
    each match. Returns the number of matched replies logged."""
    if not settings.IMAP_HOST:
        return 0  # not configured - a no-op, not an error, for demo setups without IMAP

    matched = 0
    conn = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    try:
        conn.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        conn.select(settings.IMAP_FOLDER)
        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            return 0

        for num in data[0].split():
            status, msg_data = conn.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = msg.get("Subject", "")
            body = _get_body(msg)

            code = extract_correlation_code(subject, body)
            if code is None:
                continue

            dispatch = db.query(Dispatch).filter(Dispatch.correlation_code == code).one_or_none()
            if dispatch is None:
                continue

            db.add(
                DispatchEvent(
                    dispatch_id=dispatch.id,
                    event_type="replied",
                    source="email",
                    payload={"subject": subject, "body": body[:5000]},
                )
            )
            db.commit()
            matched += 1
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        conn.logout()

    return matched
