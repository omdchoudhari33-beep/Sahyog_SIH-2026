from unittest.mock import MagicMock, patch

from app.seed_jharkhand_heis import JHARKHAND_HEIS, _placeholder_email, seed_jharkhand_heis


def test_placeholder_email_is_a_clearly_marked_pending_address():
    email = _placeholder_email("Birla Institute of Technology, Mesra")
    assert email.endswith("example-pending.ac.in")
    assert "--" not in email


def test_seed_inserts_one_registry_row_and_capability_per_entry():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None  # nothing pre-exists
    with patch("app.seed_jharkhand_heis.SessionLocal", return_value=db), \
         patch("app.seed_jharkhand_heis.embed_text", return_value=[0.1] * 384):
        result = seed_jharkhand_heis()

    expected_capabilities = sum(len(e["capabilities"]) for e in JHARKHAND_HEIS)
    assert result["institutions_inserted"] == len(JHARKHAND_HEIS)
    assert result["capabilities_inserted"] == expected_capabilities
    assert result["institutions_skipped_already_present"] == 0
    assert db.commit.called


def test_seed_skips_institutions_already_present():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = MagicMock()  # already present
    with patch("app.seed_jharkhand_heis.SessionLocal", return_value=db), \
         patch("app.seed_jharkhand_heis.embed_text", return_value=[0.1] * 384):
        result = seed_jharkhand_heis()

    assert result["institutions_inserted"] == 0
    assert result["institutions_skipped_already_present"] == len(JHARKHAND_HEIS)
