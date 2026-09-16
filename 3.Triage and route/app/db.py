from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Text,
    Float,
    Integer,
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
    __tablename__ = "active_tickets"

    id = Column(BigInteger, primary_key=True)
    master_ticket_id = Column(BigInteger, ForeignKey("active_tickets.id"), nullable=True)
    standardized_problem_statement = Column(Text, nullable=False)
    domain = Column(Text)
    urgency = Column(Text)
    severity = Column(Float)
    population_impact = Column(Float)
    status = Column(Text, nullable=False, default="active")
    cluster_count = Column(Integer, nullable=False, default=1)
    priority_score = Column(Float)
    ai_suggested_track = Column(Text)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    raw_evidence = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ColdStorage(Base):
    __tablename__ = "cold_storage"

    id = Column(BigInteger, primary_key=True)
    reason = Column(Text, nullable=False)
    raw_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
