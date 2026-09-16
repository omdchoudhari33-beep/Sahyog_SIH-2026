from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.funding import issue_nep_credit, open_ledger, record_ip_agreement, release_funds


def test_record_ip_agreement_rejects_invalid_tier():
    db = MagicMock()
    with pytest.raises(ValueError):
        record_ip_agreement(db, proposal_id=1, partner_id=1, tier="bogus_tier")


def test_record_ip_agreement_succeeds_for_valid_tier():
    db = MagicMock()
    agreement = record_ip_agreement(db, proposal_id=1, partner_id=1, tier="shared")
    assert agreement.tier == "shared"
    assert db.commit.called


def test_open_ledger_rejects_non_positive_amount():
    db = MagicMock()
    with pytest.raises(ValueError):
        open_ledger(db, proposal_id=1, partner_id=1, total_committed_amount=Decimal("0"))


def test_open_ledger_succeeds():
    db = MagicMock()
    ledger = open_ledger(db, proposal_id=1, partner_id=1, total_committed_amount=Decimal("100000"))
    assert ledger.status == "committed"
    assert db.commit.called


def test_release_funds_raises_when_ledger_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(LookupError):
        release_funds(db, ledger_id=1, amount=Decimal("100"), released_by="officer")


def test_release_funds_rejects_release_exceeding_committed_amount():
    db = MagicMock()
    ledger = MagicMock(id=1, status="committed", total_committed_amount=Decimal("1000"))
    db.query.return_value.filter.return_value.one_or_none.return_value = ledger
    db.query.return_value.filter.return_value.all.return_value = []  # no prior releases
    with pytest.raises(ValueError, match="would exceed"):
        release_funds(db, ledger_id=1, amount=Decimal("1500"), released_by="officer")


def test_release_funds_marks_fully_released_when_exact():
    db = MagicMock()
    ledger = MagicMock(id=1, status="committed", total_committed_amount=Decimal("1000"))
    db.query.return_value.filter.return_value.one_or_none.return_value = ledger
    db.query.return_value.filter.return_value.all.return_value = []
    release_funds(db, ledger_id=1, amount=Decimal("1000"), released_by="officer")
    assert ledger.status == "fully_released"


def test_release_funds_rejects_cancelled_ledger():
    db = MagicMock()
    ledger = MagicMock(id=1, status="cancelled", total_committed_amount=Decimal("1000"))
    db.query.return_value.filter.return_value.one_or_none.return_value = ledger
    with pytest.raises(ValueError, match="cancelled"):
        release_funds(db, ledger_id=1, amount=Decimal("100"), released_by="officer")


def test_issue_nep_credit_rejects_invalid_type():
    db = MagicMock()
    with pytest.raises(ValueError):
        issue_nep_credit(db, proposal_id=1, team_member_name="Student A", credit_type="bogus")


def test_issue_nep_credit_succeeds():
    db = MagicMock()
    credit = issue_nep_credit(db, proposal_id=1, team_member_name="Student A", credit_type="nep_academic_credit", credits_awarded=Decimal("2.0"))
    assert credit.credit_type == "nep_academic_credit"
    assert db.commit.called
