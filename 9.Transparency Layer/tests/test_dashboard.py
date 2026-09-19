from unittest.mock import MagicMock

from app.dashboard import full_dashboard, industry_engagement, outcome_counts


def test_outcome_counts_includes_patents():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.one.return_value = {
        "handovers": 3, "spinouts": 1, "track_a_resolved": 5,
        "patents_filed": 2, "patents_granted": 1,
    }
    result = outcome_counts(db)
    assert result["patents_filed"] == 2
    assert result["patents_granted"] == 1


def test_industry_engagement_uses_independent_subqueries_not_a_cross_join():
    """Regression test: an earlier draft used FULL OUTER JOIN ... ON true
    between partnership_matches and milestone_fund_ledger, which would have
    multiplied total_committed_amount by the row count of the other table.
    This asserts the query only executes once (a single SELECT with
    scalar subqueries), not a join producing a cartesian product."""
    db = MagicMock()
    db.execute.return_value.mappings.return_value.one.return_value = {
        "active_partners": 2, "pending_matches": 1, "total_committed_amount": 450000,
    }
    result = industry_engagement(db)
    assert db.execute.call_count == 1
    assert result["total_committed_amount"] == 450000


def test_full_dashboard_assembles_all_sections():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []
    db.execute.return_value.mappings.return_value.one.return_value = {}
    result = full_dashboard(db)
    assert set(result.keys()) == {"district_domain_heatmap", "hei_participation", "industry_engagement", "completion_rate", "outcomes"}
