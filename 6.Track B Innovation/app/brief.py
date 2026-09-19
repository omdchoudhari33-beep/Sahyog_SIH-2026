"""Renders the "problem brief" sent to every top-N matched HEI (and shown in
the University Portal / Admin Portal). One shared template so the email, the
portal, and the citizen-facing status page can never drift out of sync on
what a brief actually contains.

Pulls straight from active_tickets + media_objects, the same join
9.Transparency Layer's citizen_status.py already uses for the report photo -
duplicated here (not imported) because this is a separate deployable service
with its own DB session, same pattern every other cross-service read in this
repo follows (see matcher.py's load_ticket_for_match).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings


@dataclass
class TicketBrief:
    ticket_id: int
    problem_statement: str
    domain: Optional[str]
    severity: Optional[float]
    population_impact: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]
    photo_url: Optional[str]
    generated_at: datetime


def _media_url(bucket: Optional[str], object_key: Optional[str]) -> Optional[str]:
    if not bucket or not object_key:
        return None
    return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{bucket}/{object_key}"


def load_ticket_brief(db: Session, ticket_id: int) -> Optional[TicketBrief]:
    row = db.execute(
        text(
            """
            SELECT t.id, t.standardized_problem_statement, t.domain, t.severity, t.population_impact,
                   ST_Y(t.geom) AS latitude, ST_X(t.geom) AS longitude,
                   photo.bucket AS photo_bucket, photo.object_key AS photo_object_key
            FROM active_tickets t
            LEFT JOIN media_objects photo ON photo.id = t.report_photo_media_id
            WHERE t.id = :ticket_id
            """
        ),
        {"ticket_id": ticket_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    return TicketBrief(
        ticket_id=row["id"],
        problem_statement=row["standardized_problem_statement"],
        domain=row["domain"],
        severity=row["severity"],
        population_impact=row["population_impact"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        photo_url=_media_url(row["photo_bucket"], row["photo_object_key"]),
        generated_at=datetime.now(timezone.utc),
    )


def _severity_label(severity: Optional[float]) -> str:
    if severity is None:
        return "Not assessed"
    if severity >= 0.75:
        return "Critical"
    if severity >= 0.5:
        return "High"
    if severity >= 0.25:
        return "Moderate"
    return "Low"


def render_brief_html(brief: TicketBrief, *, hei_name: str, similarity_score: float, decide_url: str) -> str:
    """The full brief shown to a single HEI - embedded in the broadcast
    email and stored verbatim in hei_broadcast_notices.brief_html (a
    snapshot at send time, so it stays exactly what that institution saw
    even if the underlying ticket is edited later)."""
    location_line = (
        f"{brief.latitude:.5f}, {brief.longitude:.5f}"
        if brief.latitude is not None and brief.longitude is not None
        else "Not available"
    )
    photo_html = (
        f'<p><img src="{brief.photo_url}" alt="Citizen-submitted evidence photo" '
        f'style="max-width:320px;border-radius:8px;border:1px solid #e8e3d8;"/></p>'
        if brief.photo_url
        else ""
    )
    return f"""
    <div>
      <p style="color:#6d766e;font-size:12px;margin:0 0 8px;">
        SAHYOG Track B - Problem Brief - generated {brief.generated_at.strftime('%d %b %Y, %H:%M UTC')}
      </p>
      <h3 style="margin:0 0 4px;">Ticket #{brief.ticket_id}</h3>
      <p style="margin:0 0 12px;">{brief.problem_statement}</p>
      <table style="border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:2px 12px 2px 0;color:#6d766e;">Domain</td><td>{brief.domain or 'Unclassified'}</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#6d766e;">Severity</td><td>{_severity_label(brief.severity)}</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#6d766e;">Population impact</td><td>{brief.population_impact if brief.population_impact is not None else 'Not assessed'}</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#6d766e;">Location</td><td>{location_line}</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#6d766e;">Match confidence for {hei_name}</td><td>{similarity_score:.0%}</td></tr>
      </table>
      {photo_html}
      <p><a href="{decide_url}">View this opportunity / respond</a></p>
    </div>
    """
