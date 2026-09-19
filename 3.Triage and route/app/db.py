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


class MediaObject(Base):
    """Object storage registry row (MinIO / S3-compatible). Created by
    whichever service's upload path persisted the file - this service only
    reads it (to join against active_tickets.report_*_media_id), it never
    inserts rows itself."""

    __tablename__ = "media_objects"

    id = Column(BigInteger, primary_key=True)
    media_type = Column(Text, nullable=False)
    bucket = Column(Text, nullable=False)
    object_key = Column(Text, nullable=False)
    content_type = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(Text)
    original_filename = Column(Text)
    capture_lat = Column(Float)
    capture_lon = Column(Float)
    exif_captured_at = Column(DateTime(timezone=True))
    uploaded_by_service = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
    report_photo_media_id = Column(BigInteger, ForeignKey("media_objects.id"), nullable=True)
    report_audio_media_id = Column(BigInteger, ForeignKey("media_objects.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KbChunk(Base):
    """RAG knowledge-base chunk (see schema_004_kb_chunks.sql and
    app/rag_ingest.py, which populates this from knowledge_base/*.md)."""

    __tablename__ = "kb_chunks"

    id = Column(BigInteger, primary_key=True)
    source = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
