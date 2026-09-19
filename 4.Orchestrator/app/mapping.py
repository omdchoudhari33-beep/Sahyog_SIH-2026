"""
Adapters between the three agents' independently-designed schemas.

S2 (Evidence Extractor) emits Severity as an enum (LOW/MEDIUM/HIGH/CRITICAL)
and its own Track suggestion (TRACK_A/TRACK_B/UNSURE). S3 (Triage & Route)
stores severity as a float for the G1 weighted-priority formula and expects
track values as lower-case ("track_a"/"track_b"/"review_required"). This
module is the single place that bridges the two vocabularies.
"""

SEVERITY_TO_SCORE = {
    "LOW": 1.0,
    "MEDIUM": 2.0,
    "HIGH": 3.0,
    "CRITICAL": 4.0,
}

SEVERITY_TO_URGENCY = {
    "LOW": "low",
    "MEDIUM": "medium",
    "HIGH": "high",
    "CRITICAL": "high",
}

TRACK_TO_TICKET_VALUE = {
    "TRACK_A": "track_a",
    "TRACK_B": "track_b",
    "UNSURE": "review_required",
}


def severity_to_score(severity: str | None) -> float:
    return SEVERITY_TO_SCORE.get((severity or "").upper(), 1.0)


def severity_to_urgency(severity: str | None) -> str:
    return SEVERITY_TO_URGENCY.get((severity or "").upper(), "low")


def track_to_ticket_value(track: str | None) -> str:
    return TRACK_TO_TICKET_VALUE.get((track or "").upper(), "review_required")


def build_ticket_payload(
    structured_evidence: dict,
    latitude: float,
    longitude: float,
    raw_evidence: dict,
    default_population_impact: float,
    report_photo_media_id: int | None = None,
    report_audio_media_id: int | None = None,
) -> dict:
    """Shared IncomingTicket builder for Agent 3 - used by both the one-shot
    /submit flow and the conversational flow's finalize step.

    report_photo_media_id / report_audio_media_id are FKs into the shared
    media_objects object storage registry (see "3.Triage and route/
    schema_003_media_objects.sql") - the durable copies of whatever photo/
    audio the citizen actually submitted, when Agent 1/Agent 2 persisted one.
    """
    severity = structured_evidence["severity"]
    return {
        "standardized_problem_statement": structured_evidence["normalized_english"],
        "domain": structured_evidence["civic_domain"],
        "urgency": severity_to_urgency(severity),
        "severity": severity_to_score(severity),
        "population_impact": default_population_impact,
        "latitude": latitude,
        "longitude": longitude,
        "ai_suggested_track": track_to_ticket_value(structured_evidence["suggested_track"]),
        "raw_evidence": raw_evidence,
        "report_photo_media_id": report_photo_media_id,
        "report_audio_media_id": report_audio_media_id,
    }
