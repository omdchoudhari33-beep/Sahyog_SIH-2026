from unittest.mock import MagicMock, patch

from app.auth import verify_password
from app.onboarding import onboard_hei


def test_onboard_hei_computes_and_stores_capability_embedding():
    db = MagicMock()
    with patch("app.onboarding.embed_text", return_value=[0.1] * 384) as mock_embed:
        hei, capability, password = onboard_hei(
            db, institution_name="Demo Institute", state="Jharkhand", district=None,
            contact_email="hei@example.com", contact_phone=None, incubator_name=None,
            capacity_active_projects=3, domain="roads_bridges", department_name="Civil Engg",
            description="Road and drainage R&D",
        )
    mock_embed.assert_called_once_with("Road and drainage R&D")
    assert capability.domain == "ROADS_BRIDGES"  # normalized to upper-case
    assert db.commit.called


def test_onboard_hei_generates_a_working_password_when_none_given():
    db = MagicMock()
    with patch("app.onboarding.embed_text", return_value=[0.1] * 384):
        hei, capability, password = onboard_hei(
            db, institution_name="Demo Institute", state="Jharkhand", district=None,
            contact_email="hei@example.com", contact_phone=None, incubator_name=None,
            capacity_active_projects=3, domain="ROADS_BRIDGES", department_name="Civil Engg",
            description="Road R&D",
        )
    assert password  # a real plaintext password was generated
    assert verify_password(password, hei.password_hash)  # and its hash actually verifies against it


def test_onboard_hei_respects_an_explicit_password():
    db = MagicMock()
    with patch("app.onboarding.embed_text", return_value=[0.1] * 384):
        hei, capability, password = onboard_hei(
            db, institution_name="Demo Institute", state="Jharkhand", district=None,
            contact_email="hei@example.com", contact_phone=None, incubator_name=None,
            capacity_active_projects=3, domain="ROADS_BRIDGES", department_name="Civil Engg",
            description="Road R&D", initial_password="my-chosen-password",
        )
    assert password == "my-chosen-password"
    assert verify_password("my-chosen-password", hei.password_hash)
