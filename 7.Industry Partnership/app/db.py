from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Text,
    Numeric,
    Integer,
    Boolean,
    ForeignKey,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class ActiveTicket(Base):
    """Read-only mapping onto the table owned by 3.Triage and route - only
    the domain column, needed to match a proposal to a partner capability."""

    __tablename__ = "active_tickets"

    id = Column(BigInteger, primary_key=True)
    domain = Column(Text)


class Proposal(Base):
    """Read-only mapping onto the table owned by 6.Track B Innovation - only
    the columns this service actually reads. Never migrated/created here."""

    __tablename__ = "proposals"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    requested_budget = Column(Numeric(12, 2))
    status = Column(Text, nullable=False, default="submitted")


class Partner(Base):
    __tablename__ = "partners"

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    sector = Column(Text)
    contact_name = Column(Text)
    contact_email = Column(Text, nullable=False)
    contact_phone = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnerCapability(Base):
    __tablename__ = "partner_capabilities"

    id = Column(BigInteger, primary_key=True)
    partner_id = Column(BigInteger, ForeignKey("partners.id"), nullable=False)
    domain = Column(Text, nullable=False)
    offering_type = Column(Text, nullable=False)
    notes = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnershipMatch(Base):
    __tablename__ = "partnership_matches"

    id = Column(BigInteger, primary_key=True)
    proposal_id = Column(BigInteger, nullable=False)
    partner_id = Column(BigInteger, ForeignKey("partners.id"), nullable=False)
    match_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="proposed")
    match_token = Column(Text, nullable=False, unique=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IpAgreement(Base):
    __tablename__ = "ip_agreements"

    id = Column(BigInteger, primary_key=True)
    proposal_id = Column(BigInteger, nullable=False)
    partner_id = Column(BigInteger, ForeignKey("partners.id"), nullable=True)
    tier = Column(Text, nullable=False)
    template_version = Column(Text, nullable=False, default="v1-placeholder")
    document_url = Column(Text)
    agreed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MilestoneFundLedger(Base):
    __tablename__ = "milestone_fund_ledger"

    id = Column(BigInteger, primary_key=True)
    proposal_id = Column(BigInteger, nullable=False)
    partner_id = Column(BigInteger, ForeignKey("partners.id"), nullable=True)
    total_committed_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(Text, nullable=False, default="INR")
    status = Column(Text, nullable=False, default="committed")
    escrow_provider = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FundRelease(Base):
    __tablename__ = "fund_releases"

    id = Column(BigInteger, primary_key=True)
    ledger_id = Column(BigInteger, ForeignKey("milestone_fund_ledger.id"), nullable=False)
    milestone_id = Column(BigInteger, nullable=True)
    amount_released = Column(Numeric(12, 2), nullable=False)
    released_by = Column(Text, nullable=False)
    released_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NepCredit(Base):
    __tablename__ = "nep_credits"

    id = Column(BigInteger, primary_key=True)
    proposal_id = Column(BigInteger, nullable=False)
    team_member_name = Column(Text, nullable=False)
    credit_type = Column(Text, nullable=False)
    credits_awarded = Column(Numeric(5, 2))
    certificate_url = Column(Text)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
