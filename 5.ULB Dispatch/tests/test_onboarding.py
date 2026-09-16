from unittest.mock import MagicMock

import pytest

from app.onboarding import onboard_contact


def test_onboard_contact_raises_when_ulb_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(LookupError):
        onboard_contact(db, ulb_id=999, domain=None, dept_name="Roads", officer_name=None, officer_phone=None, email="a@b.com")


def test_onboard_contact_sets_verified_at_immediately_trust_on_registration():
    """Documents the deliberate hackathon shortcut: verified_at is set on
    submission, not after a real OTP/verification flow. See module TODO."""
    db = MagicMock()
    ulb = MagicMock(id=1)
    db.query.return_value.filter.return_value.one_or_none.return_value = ulb

    contact = onboard_contact(
        db, ulb_id=1, domain="roads_bridges", dept_name="Roads Dept",
        officer_name="Officer A", officer_phone="9999999999", email="officer@ulb.gov.in",
    )

    assert contact.verified_at is not None
    assert contact.domain == "ROADS_BRIDGES"  # normalized to upper-case
    assert db.commit.called


def test_onboard_contact_normalizes_blank_domain_to_catch_all():
    db = MagicMock()
    ulb = MagicMock(id=1)
    db.query.return_value.filter.return_value.one_or_none.return_value = ulb

    contact = onboard_contact(
        db, ulb_id=1, domain="  ", dept_name="General Office", officer_name=None,
        officer_phone=None, email="office@ulb.gov.in",
    )

    assert contact.domain is None
