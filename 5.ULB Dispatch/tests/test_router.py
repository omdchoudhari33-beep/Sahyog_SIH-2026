from unittest.mock import MagicMock

import pytest

from app.router import (
    AmbiguousUlbMatchError,
    NoContactForDomainError,
    NoUlbMatchError,
    resolve_contacts,
)


def _fake_ticket_row(domain="ROADS_BRIDGES"):
    return {"geom": "POINT(85.3 23.3)", "domain": domain}


def _make_db(ticket_row, ulb_rows, contact_rows, contact_objects):
    db = MagicMock()

    def execute_side_effect(stmt, params=None):
        sql = str(stmt)
        result = MagicMock()
        if "FROM active_tickets" in sql:
            result.mappings.return_value.one_or_none.return_value = ticket_row
        elif "FROM ulb_directory" in sql:
            result.mappings.return_value.all.return_value = ulb_rows
        elif "FROM ulb_contacts" in sql:
            result.mappings.return_value.all.return_value = contact_rows
        return result

    db.execute.side_effect = execute_side_effect
    db.query.return_value.filter.return_value.all.return_value = contact_objects
    return db


def test_resolve_contacts_raises_when_no_ulb_matches():
    db = _make_db(_fake_ticket_row(), ulb_rows=[], contact_rows=[], contact_objects=[])
    with pytest.raises(NoUlbMatchError):
        resolve_contacts(db, ticket_id=1)


def test_resolve_contacts_raises_on_ambiguous_ulb_match():
    db = _make_db(_fake_ticket_row(), ulb_rows=[{"id": 1}, {"id": 2}], contact_rows=[], contact_objects=[])
    with pytest.raises(AmbiguousUlbMatchError):
        resolve_contacts(db, ticket_id=1)


def test_resolve_contacts_falls_back_to_catch_all_contact():
    """Verified against real ULB data shape: one catch-all (domain IS NULL)
    row, no domain-specific rows - this is the common case, not an edge case."""
    catch_all = MagicMock(id=99, ulb_id=1, domain=None, channel="email")
    db = _make_db(
        _fake_ticket_row(domain="ROADS_BRIDGES"),
        ulb_rows=[{"id": 1}],
        contact_rows=[{"id": 99, "domain": None}],
        contact_objects=[catch_all],
    )
    result = resolve_contacts(db, ticket_id=1, level=1)
    assert len(result) == 1
    assert result[0].id == 99
    assert result[0].domain is None


def test_resolve_contacts_prefers_exact_domain_over_catch_all():
    exact = MagicMock(id=1, ulb_id=1, domain="ROADS_BRIDGES", channel="email")
    catch_all = MagicMock(id=2, ulb_id=1, domain=None, channel="email")
    db = _make_db(
        _fake_ticket_row(domain="ROADS_BRIDGES"),
        ulb_rows=[{"id": 1}],
        # ORDER BY (domain IS NOT NULL) DESC -> exact-domain row comes first
        contact_rows=[{"id": 1, "domain": "ROADS_BRIDGES"}],
        contact_objects=[exact, catch_all],
    )
    result = resolve_contacts(db, ticket_id=1, level=1)
    assert len(result) == 1
    assert result[0].id == 1


def test_resolve_contacts_raises_when_truly_unconfigured():
    db = _make_db(_fake_ticket_row(), ulb_rows=[{"id": 1}], contact_rows=[], contact_objects=[])
    with pytest.raises(NoContactForDomainError):
        resolve_contacts(db, ticket_id=1)
