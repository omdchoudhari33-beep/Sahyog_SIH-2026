"""F2 Pilot Validation. Same shape as 5.ULB Dispatch's closure.py:
verify_closure() - geo-check + optional vision hook, never auto-resolves on
ambiguous signals. Duplicates (does not cross-import) the small haversine
helper, per this repo's "each service stays independently deployable" idiom.
"""
from __future__ import annotations

import math
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import PilotValidation, RdOutcomeFeedback

EARTH_RADIUS_METERS = 6_371_000.0


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def _get_vision_similarity(photo_bytes: bytes, ticket_problem_statement: str) -> Optional[float]:
    """# TODO(human): same caveat as 5.ULB Dispatch/app/closure.py - confirm
    the exact request/response shape against 2.Evidence Extractor's actual
    contract, and get a human decision on the right prompt/interpretation
    for "does this pilot photo show the R&D fix actually working", which is
    a different question than that endpoint's original "does this photo
    match a new complaint" use case."""
    if not settings.VISION_CLASSIFIER_URL:
        return None
    try:
        response = httpx.post(
            settings.VISION_CLASSIFIER_URL,
            files={"image": ("pilot.jpg", photo_bytes)},
            data={"normalized_english": ticket_problem_statement},
            timeout=60.0,
        )
        response.raise_for_status()
        body = response.json()
        return float(body.get("visual_evidence", {}).get("confidence")) if body.get("visual_evidence") else None
    except Exception:  # noqa: BLE001 - never let a vision-service outage block validation
        return None


def verify_pilot(
    db: Session, ticket_id: int, proposal_id: int, photo_bytes: bytes, photo_url: str,
    photo_media_id: Optional[int], photo_lat: Optional[float], photo_lon: Optional[float],
) -> PilotValidation:
    ticket_row = db.execute(
        text("SELECT standardized_problem_statement, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon FROM active_tickets WHERE id = :ticket_id"),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if ticket_row is None:
        raise LookupError(f"active_tickets row {ticket_id} was not found")

    geo_check_passed: Optional[bool] = None
    if photo_lat is not None and photo_lon is not None and ticket_row["lat"] is not None and ticket_row["lon"] is not None:
        distance = haversine_meters(photo_lat, photo_lon, ticket_row["lat"], ticket_row["lon"])
        geo_check_passed = distance <= settings.CLOSURE_GEO_RADIUS_METERS

    similarity_score = _get_vision_similarity(photo_bytes, ticket_row["standardized_problem_statement"])

    vision_indicates_pass = similarity_score is not None and similarity_score >= 0.5
    vision_skipped = similarity_score is None

    if bool(geo_check_passed) and (vision_indicates_pass or vision_skipped):
        verdict = "pass"
    elif geo_check_passed is False:
        verdict = "fail"
    else:
        verdict = "pending_review"

    validation = PilotValidation(
        ticket_id=ticket_id, proposal_id=proposal_id, photo_url=photo_url,
        photo_media_id=photo_media_id,
        photo_lat=photo_lat, photo_lon=photo_lon, geo_check_passed=geo_check_passed,
        similarity_score=similarity_score, verdict=verdict,
    )
    db.add(validation)

    if verdict in ("pass", "fail"):
        db.add(RdOutcomeFeedback(
            ticket_id=ticket_id, outcome="pilot_pass" if verdict == "pass" else "pilot_fail",
            notes=f"proposal_id={proposal_id}, geo_check_passed={geo_check_passed}, similarity_score={similarity_score}",
        ))

    db.commit()
    db.refresh(validation)
    return validation
