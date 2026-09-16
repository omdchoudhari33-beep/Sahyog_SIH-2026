from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Text,
    Float,
    Integer,
    Boolean,
    Date,
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
    the columns this service actually reads. Never migrated/created here."""

    __tablename__ = "active_tickets"

    id = Column(BigInteger, primary_key=True)
    domain = Column(Text)
    status = Column(Text, nullable=False, default="active")


class Proposal(Base):
    """Read-only mapping onto the table owned by 6.Track B Innovation."""

    __tablename__ = "proposals"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, nullable=False)
    title = Column(Text, nullable=False)
    timeline_weeks = Column(Integer)
    status = Column(Text, nullable=False, default="submitted")


class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(BigInteger, primary_key=True)
    proposal_id = Column(BigInteger, nullable=False)
    sequence_no = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    target_date = Column(Date)
    status = Column(Text, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MilestoneEvaluation(Base):
    __tablename__ = "milestone_evaluations"

    id = Column(BigInteger, primary_key=True)
    milestone_id = Column(BigInteger, ForeignKey("milestones.id"), nullable=False)
    evaluator_name = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    notes = Column(Text)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())


class PilotValidation(Base):
    __tablename__ = "pilot_validations"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    proposal_id = Column(BigInteger, nullable=False)
    photo_url = Column(Text, nullable=False)
    photo_lat = Column(Float)
    photo_lon = Column(Float)
    geo_check_passed = Column(Boolean)
    similarity_score = Column(Float)
    verdict = Column(Text, nullable=False, default="pending_review")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HandoverRecord(Base):
    __tablename__ = "handover_records"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    ulb_dispatch_id = Column(BigInteger, nullable=True)
    handover_notes = Column(Text)
    handed_over_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SpinoutRecord(Base):
    __tablename__ = "spinout_records"

    id = Column(BigInteger, primary_key=True)
    proposal_id = Column(BigInteger, nullable=False)
    startup_name = Column(Text, nullable=False)
    incubator_name = Column(Text)
    notes = Column(Text)
    spun_out_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RdOutcomeFeedback(Base):
    __tablename__ = "rd_outcome_feedback"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    outcome = Column(Text, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
