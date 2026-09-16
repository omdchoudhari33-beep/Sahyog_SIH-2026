from sqlalchemy import create_engine, Column, BigInteger, Text, JSON, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True)
    service_name = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(BigInteger, nullable=False)
    event = Column(Text, nullable=False)
    actor = Column(Text)
    payload = Column(JSON)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
