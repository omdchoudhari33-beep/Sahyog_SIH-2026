"""X1 Govt Analytics Dashboard - real aggregate SQL across every other
service's tables (same DB instance, read-only). Assumes services 3, 5, 6, 7,
8's migrations have all been applied - this service is built last and
depends on them existing, per the integration plan."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def district_domain_heatmap(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT COALESCE(u.district, 'unassigned') AS district, t.domain, COUNT(*) AS ticket_count
            FROM active_tickets t
            LEFT JOIN ulb_directory u ON u.active AND ST_Contains(u.boundary, t.geom)
            GROUP BY district, t.domain
            ORDER BY ticket_count DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def hei_participation(db: Session) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(DISTINCT hei_id) FILTER (WHERE status = 'accepted') AS active_heis,
                COUNT(*) FILTER (WHERE status = 'proposed') AS pending_matches,
                COUNT(*) FILTER (WHERE status = 'declined') AS declined_matches
            FROM hei_matches
            """
        )
    ).mappings().one()
    return dict(row)


def industry_engagement(db: Session) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(DISTINCT partner_id) FROM partnership_matches WHERE status = 'accepted') AS active_partners,
                (SELECT COUNT(*) FROM partnership_matches WHERE status = 'proposed') AS pending_matches,
                (SELECT COALESCE(SUM(total_committed_amount), 0) FROM milestone_fund_ledger) AS total_committed_amount
            """
        )
    ).mappings().one()
    return dict(row)


def completion_rate(db: Session) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE verdict = 'pass') AS pilots_passed,
                COUNT(*) FILTER (WHERE verdict = 'fail') AS pilots_failed,
                COUNT(*) FILTER (WHERE verdict = 'pending_review') AS pilots_pending
            FROM pilot_validations
            """
        )
    ).mappings().one()
    return dict(row)


def outcome_counts(db: Session) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM handover_records) AS handovers,
                (SELECT COUNT(*) FROM spinout_records) AS spinouts,
                (SELECT COUNT(*) FROM dispatches WHERE status = 'resolved') AS track_a_resolved,
                (SELECT COUNT(*) FROM patent_records) AS patents_filed,
                (SELECT COUNT(*) FROM patent_records WHERE filing_status = 'granted') AS patents_granted
            """
        )
    ).mappings().one()
    return dict(row)


def full_dashboard(db: Session) -> dict:
    return {
        "district_domain_heatmap": district_domain_heatmap(db),
        "hei_participation": hei_participation(db),
        "industry_engagement": industry_engagement(db),
        "completion_rate": completion_rate(db),
        "outcomes": outcome_counts(db),
    }
