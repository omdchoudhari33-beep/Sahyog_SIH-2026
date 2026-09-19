from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Text,
    Float,
    Integer,
    Boolean,
    Numeric,
    ForeignKey,
    JSON,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class ActiveTicket(Base):
    """Read-only mapping onto the table owned by 3.Triage and route - only
    the columns this service actually reads, including the embedding
    Agent3 already computed (reused directly, never re-embedded here)."""

    __tablename__ = "active_tickets"

    id = Column(BigInteger, primary_key=True)
    domain = Column(Text)
    standardized_problem_statement = Column(Text, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    status = Column(Text, nullable=False, default="active")


class MediaObject(Base):
    """Read-only mapping onto the table owned by "3.Triage and route" (see
    its schema_003_media_objects.sql) - only the PK. This service never
    creates/queries rows through the ORM (see app/storage.py, which inserts
    via raw SQL like every other service's copy of object_storage.py) -
    this class exists purely so ForeignKey("media_objects.id") on
    Proposal.solution_document_media_id below has a real mapped table to
    resolve against; SQLAlchemy's declarative FK resolution fails at
    startup without it, even though no code here ever queries through it."""

    __tablename__ = "media_objects"

    id = Column(BigInteger, primary_key=True)


class HeiRegistry(Base):
    __tablename__ = "hei_registry"

    id = Column(BigInteger, primary_key=True)
    institution_name = Column(Text, nullable=False)
    state = Column(Text, nullable=False)
    district = Column(Text)
    contact_email = Column(Text, nullable=False)
    contact_phone = Column(Text)
    incubator_name = Column(Text)
    capacity_active_projects = Column(Integer, nullable=False, default=3)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    password_hash = Column(Text, nullable=True)  # NULL until onboarding sets it - see app/auth.py


class HeiSession(Base):
    __tablename__ = "hei_sessions"

    id = Column(BigInteger, primary_key=True)
    hei_id = Column(BigInteger, ForeignKey("hei_registry.id"), nullable=False)
    session_token = Column(Text, nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HeiCapability(Base):
    __tablename__ = "hei_capabilities"

    id = Column(BigInteger, primary_key=True)
    hei_id = Column(BigInteger, ForeignKey("hei_registry.id"), nullable=False)
    domain = Column(Text, nullable=False)
    department_name = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HeiMatch(Base):
    __tablename__ = "hei_matches"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    hei_id = Column(BigInteger, ForeignKey("hei_registry.id"), nullable=False)
    capability_id = Column(BigInteger, ForeignKey("hei_capabilities.id"), nullable=True)
    similarity_score = Column(Float)
    status = Column(Text, nullable=False, default="proposed")
    decline_reason = Column(Text)
    attempt_no = Column(Integer, nullable=False, default=1)
    match_token = Column(Text, nullable=False, unique=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HeiBroadcastNotice(Base):
    """Informational fan-out of a ticket's problem brief to the top-N
    matching HEIs (see schema_003_hei_broadcast.sql) - independent of
    HeiMatch's single-active-match accept/decline state machine."""

    __tablename__ = "hei_broadcast_notices"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    hei_id = Column(BigInteger, ForeignKey("hei_registry.id"), nullable=False)
    capability_id = Column(BigInteger, ForeignKey("hei_capabilities.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    similarity_score = Column(Float, nullable=False)
    brief_html = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "teams"

    id = Column(BigInteger, primary_key=True)
    match_id = Column(BigInteger, ForeignKey("hei_matches.id"), nullable=False)
    team_name = Column(Text, nullable=False)
    faculty_mentor_name = Column(Text, nullable=False)
    faculty_mentor_email = Column(Text, nullable=False)
    student_names = Column(JSON, nullable=False, default=list)
    formed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(BigInteger, primary_key=True)
    team_id = Column(BigInteger, ForeignKey("teams.id"), nullable=False)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    requested_budget = Column(Numeric(12, 2))
    timeline_weeks = Column(Integer)
    status = Column(Text, nullable=False, default="submitted")
    nodal_officer_id = Column(Text)
    nodal_notes = Column(Text)
    solution_document_media_id = Column(BigInteger, ForeignKey("media_objects.id"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
