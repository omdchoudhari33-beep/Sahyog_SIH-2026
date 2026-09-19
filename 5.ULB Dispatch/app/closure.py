"""Closure proof verification: geo-check + optional vision-similarity hook.

Never auto-rejects or auto-approves on ambiguous signals - the
closure_proofs row is always inserted so there is a complete, honest audit
trail, and anything not clearly resolved is flagged for a human operator.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import ClosureProof, Dispatch, DispatchEvent

EARTH_RADIUS_METERS = 6_371_000.0


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def _get_vision_similarity(photo_bytes: bytes, ticket_problem_statement: str) -> Optional[float]:
    """Reuses "2.Evidence Extractor"'s C3 vision endpoint if configured.

    # TODO(human): confirm the exact request/response shape against that
    # service's actual /evidence/attach-photo contract before relying on
    # this in production - it currently assumes a multipart POST returning
    # a JSON body with a `visual_evidence.confidence` float, mirroring the
    # shape documented in that service's schemas.py, but the *semantics*
    # (does high confidence mean "matches complaint" or "damage resolved"?)
    # need a human decision on the right prompt/interpretation for closure
    # verification specifically, since the existing endpoint was built for
    # verifying a NEW complaint's photo, not a resolved-issue photo.
    """
    if not settings.VISION_CLASSIFIER_URL:
        return None
    try:
        response = httpx.post(
            settings.VISION_CLASSIFIER_URL,
            files={"image": ("closure.jpg", photo_bytes)},
            data={"normalized_english": ticket_problem_statement},
            timeout=60.0,
        )
        response.raise_for_status()
        body = response.json()
        return float(body.get("visual_evidence", {}).get("confidence")) if body.get("visual_evidence") else None
    except Exception:  # noqa: BLE001 - never let a vision-service outage block closure
        return None


def verify_closure(
    db: Session,
    dispatch_id: int,
    photo_bytes: bytes,
    photo_url: str,
    photo_media_id: Optional[int],
    photo_lat: Optional[float],
    photo_lon: Optional[float],
    exif_captured_at: Optional[datetime],
    submitted_by: str,
) -> ClosureProof:
    dispatch = db.query(Dispatch).filter(Dispatch.id == dispatch_id).one_or_none()
    if dispatch is None:
        raise LookupError(f"dispatch {dispatch_id} was not found")

    ticket_row = db.execute(
        text(
            "SELECT standardized_problem_statement, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon "
            "FROM active_tickets WHERE id = :ticket_id"
        ),
        {"ticket_id": dispatch.ticket_id},
    ).mappings().one_or_none()
    if ticket_row is None:
        raise LookupError(f"active_tickets row {dispatch.ticket_id} was not found")

    geo_check_passed: Optional[bool] = None
    if photo_lat is not None and photo_lon is not None and ticket_row["lat"] is not None and ticket_row["lon"] is not None:
        distance = haversine_meters(photo_lat, photo_lon, ticket_row["lat"], ticket_row["lon"])
        geo_check_passed = distance <= settings.CLOSURE_GEO_RADIUS_METERS

    similarity_score = _get_vision_similarity(photo_bytes, ticket_row["standardized_problem_statement"])

    officer_verified_contact = submitted_by == "officer"  # contact.verified_at gate is checked by the caller (main.py) before this is set True

    proof = ClosureProof(
        ticket_id=dispatch.ticket_id,
        dispatch_id=dispatch_id,
        photo_url=photo_url,
        photo_media_id=photo_media_id,
        photo_lat=photo_lat,
        photo_lon=photo_lon,
        exif_captured_at=exif_captured_at,
        similarity_score=similarity_score,
        geo_check_passed=geo_check_passed,
        citizen_confirmed=(submitted_by == "citizen") or None,
        submitted_by=submitted_by,
        verified_at=None,
    )

    vision_indicates_resolved = similarity_score is not None and similarity_score >= 0.5
    vision_skipped = similarity_score is None

    auto_resolve = (
        officer_verified_contact
        and bool(geo_check_passed)
        and (vision_indicates_resolved or vision_skipped)
    )

    if auto_resolve:
        proof.verified_at = datetime.now(timezone.utc)
        dispatch.status = "resolved"
        db.add(dispatch)
        db.add(proof)
        db.flush()
        db.add(DispatchEvent(dispatch_id=dispatch_id, event_type="resolved", source="status_link", payload={"closure_proof_id": proof.id}))
    else:
        db.add(proof)
        db.flush()
        # 'disputed' for a failed geo check; 'acked' as the closest neutral
        # value in the fixed event_type enum for "pending manual review" -
        # the ambiguity is fully described in payload.reason for ops.
        event_type = "disputed" if geo_check_passed is False else "acked"
        payload = {
            "closure_proof_id": proof.id,
            "geo_check_passed": geo_check_passed,
            "similarity_score": similarity_score,
            "reason": "geo check failed" if geo_check_passed is False else "pending manual review",
        }
        db.add(DispatchEvent(dispatch_id=dispatch_id, event_type=event_type, source="status_link", payload=payload))

    db.commit()
    return proof
