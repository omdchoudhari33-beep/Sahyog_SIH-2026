"""I3 Tiered IP Ownership Template, I4 Milestone Fund Ledger, I5 NEP Academic
Credit & CSR Certificate.

None of these move real money, sign real documents, or issue real academic
credit - they record that a decision/commitment/issuance happened and by
whom, giving a real audit trail to build a real integration against later.
See README for the full TODO(human) list.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.audit import log_audit_event

from app.db import FundRelease, IpAgreement, MilestoneFundLedger, NepCredit


VALID_TIERS = {"hei_owned", "shared", "partner_owned", "open_source"}


def record_ip_agreement(db: Session, proposal_id: int, partner_id: Optional[int], tier: str, document_url: Optional[str] = None) -> IpAgreement:
    if tier not in VALID_TIERS:
        raise ValueError(f"tier must be one of: {', '.join(sorted(VALID_TIERS))}")
    agreement = IpAgreement(proposal_id=proposal_id, partner_id=partner_id, tier=tier, document_url=document_url)
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement


def open_ledger(db: Session, proposal_id: int, partner_id: Optional[int], total_committed_amount: Decimal, escrow_provider: Optional[str] = None) -> MilestoneFundLedger:
    if total_committed_amount <= 0:
        raise ValueError("total_committed_amount must be positive")
    ledger = MilestoneFundLedger(
        proposal_id=proposal_id, partner_id=partner_id, total_committed_amount=total_committed_amount,
        status="committed", escrow_provider=escrow_provider,
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


def release_funds(db: Session, ledger_id: int, amount: Decimal, released_by: str, milestone_id: Optional[int] = None) -> FundRelease:
    ledger = db.query(MilestoneFundLedger).filter(MilestoneFundLedger.id == ledger_id).one_or_none()
    if ledger is None:
        raise LookupError(f"milestone_fund_ledger row {ledger_id} was not found")
    if ledger.status == "cancelled":
        raise ValueError(f"ledger {ledger_id} is cancelled, cannot release funds")

    already_released = sum(
        (r.amount_released for r in db.query(FundRelease).filter(FundRelease.ledger_id == ledger_id).all()),
        Decimal("0"),
    )
    if already_released + amount > ledger.total_committed_amount:
        raise ValueError(
            f"release of {amount} would exceed committed amount "
            f"({already_released} already released of {ledger.total_committed_amount})"
        )

    release = FundRelease(ledger_id=ledger_id, amount_released=amount, released_by=released_by, milestone_id=milestone_id)
    db.add(release)

    new_total_released = already_released + amount
    ledger.status = "fully_released" if new_total_released == ledger.total_committed_amount else "partially_released"
    db.add(ledger)

    db.commit()
    db.refresh(release)
    log_audit_event("milestone_fund_ledger", ledger_id, "funds_released", actor=released_by, payload={"amount": str(amount), "new_status": ledger.status})
    return release


def issue_nep_credit(db: Session, proposal_id: int, team_member_name: str, credit_type: str, credits_awarded: Optional[Decimal] = None, certificate_url: Optional[str] = None) -> NepCredit:
    if credit_type not in ("nep_academic_credit", "csr_certificate"):
        raise ValueError("credit_type must be nep_academic_credit or csr_certificate")
    credit = NepCredit(
        proposal_id=proposal_id, team_member_name=team_member_name, credit_type=credit_type,
        credits_awarded=credits_awarded, certificate_url=certificate_url,
    )
    db.add(credit)
    db.commit()
    db.refresh(credit)
    return credit
