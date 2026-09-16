from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Text,
    Float,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geometry

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class ActiveTicket(Base):
    """Read-only mapping onto the table owned by 3.Triage and route - this
    service never creates/migrates it, only queries the columns it needs."""

    __tablename__ = "active_tickets"

    id = Column(BigInteger, primary_key=True)
    domain = Column(Text)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    status = Column(Text, nullable=False, default="active")
    standardized_problem_statement = Column(Text, nullable=False)
    population_impact = Column(Float)
    severity = Column(Float)


class UlbDirectory(Base):
    __tablename__ = "ulb_directory"

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    state = Column(Text, nullable=False)
    district = Column(Text)
    boundary = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UlbContact(Base):
    __tablename__ = "ulb_contacts"

    id = Column(BigInteger, primary_key=True)
    ulb_id = Column(BigInteger, ForeignKey("ulb_directory.id"), nullable=False)
    domain = Column(Text, nullable=True)
    dept_name = Column(Text, nullable=False)
    level = Column(Integer, nullable=False, default=1)
    channel = Column(Text, nullable=False)
    email = Column(Text)
    api_endpoint = Column(Text)
    api_key_ref = Column(Text)
    officer_name = Column(Text)
    officer_phone = Column(Text)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EscalationMatrix(Base):
    __tablename__ = "escalation_matrix"

    id = Column(BigInteger, primary_key=True)
    domain = Column(Text, nullable=False)
    level = Column(Integer, nullable=False)
    sla_hours = Column(Integer, nullable=False)


class Dispatch(Base):
    __tablename__ = "dispatches"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    ulb_id = Column(BigInteger, ForeignKey("ulb_directory.id"), nullable=False)
    contact_id = Column(BigInteger, ForeignKey("ulb_contacts.id"), nullable=False)
    channel = Column(Text, nullable=False)
    correlation_code = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False, default="sent")
    level = Column(Integer, nullable=False, default=1)
    attempt_no = Column(Integer, nullable=False, default=1)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DispatchEvent(Base):
    __tablename__ = "dispatch_events"

    id = Column(BigInteger, primary_key=True)
    dispatch_id = Column(BigInteger, ForeignKey("dispatches.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(JSON)
    source = Column(Text, nullable=False)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())


class ClosureProof(Base):
    __tablename__ = "closure_proofs"

    id = Column(BigInteger, primary_key=True)
    ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=False)
    dispatch_id = Column(BigInteger, ForeignKey("dispatches.id"), nullable=False)
    photo_url = Column(Text, nullable=False)
    photo_lat = Column(Float)
    photo_lon = Column(Float)
    exif_captured_at = Column(DateTime(timezone=True))
    similarity_score = Column(Float)
    geo_check_passed = Column(Boolean)
    citizen_confirmed = Column(Boolean)
    submitted_by = Column(Text, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StatusLinkToken(Base):
    __tablename__ = "status_link_tokens"

    id = Column(BigInteger, primary_key=True)
    dispatch_id = Column(BigInteger, ForeignKey("dispatches.id"), nullable=False)
    token = Column(Text, nullable=False, unique=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
