from unittest.mock import MagicMock

import pytest

from app.onboarding import onboard_partner


def test_onboard_partner_rejects_invalid_type():
    db = MagicMock()
    with pytest.raises(ValueError):
        onboard_partner(db, name="X", type_="bogus", sector=None, contact_name=None, contact_email="a@b.com", contact_phone=None, domain="ROADS_BRIDGES", offering_type="mentorship")


def test_onboard_partner_rejects_invalid_offering_type():
    db = MagicMock()
    with pytest.raises(ValueError):
        onboard_partner(db, name="X", type_="industry", sector=None, contact_name=None, contact_email="a@b.com", contact_phone=None, domain="ROADS_BRIDGES", offering_type="bogus")


def test_onboard_partner_normalizes_domain_to_upper_case():
    db = MagicMock()
    partner, capability = onboard_partner(
        db, name="Demo Co", type_="industry", sector="construction", contact_name="A",
        contact_email="a@b.com", contact_phone=None, domain="roads_bridges", offering_type="both",
    )
    assert capability.domain == "ROADS_BRIDGES"
    assert db.commit.called
