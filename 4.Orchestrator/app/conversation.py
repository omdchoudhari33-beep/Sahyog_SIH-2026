"""
In-memory conversation session store for the multi-turn citizen report flow.

Not persisted - restarting the orchestrator loses in-progress conversations.
Fine for a hackathon demo; swap for Redis/DB before any real deployment.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

SessionState = Literal[
    "awaiting_confirmation",
    "awaiting_photo",
    "awaiting_location",
    "ready",
    "completed",
]


@dataclass
class ConversationSession:
    session_id: str
    state: SessionState = "awaiting_confirmation"
    source_language: Optional[str] = None

    # Populated after the "describe" step (S1 + S2's C1 classification)
    normalized_english: Optional[str] = None
    structured_evidence: Optional[dict[str, Any]] = None

    # Populated after the "photo" step (S2's C2 + C3)
    geolocation: Optional[dict[str, Any]] = None
    visual_evidence: Optional[dict[str, Any]] = None

    # Populated by the "location" step if the photo had no usable GPS
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    ticket: Optional[dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_sessions: dict[str, ConversationSession] = {}


def create_session() -> ConversationSession:
    session = ConversationSession(session_id=uuid.uuid4().hex)
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> ConversationSession:
    session = _sessions.get(session_id)
    if session is None:
        raise KeyError(f"Unknown or expired session: {session_id}")
    return session
