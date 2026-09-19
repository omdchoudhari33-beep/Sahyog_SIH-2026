import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/dno_triage",
    )

    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_ADDRESS: str = os.getenv("SMTP_FROM_ADDRESS", "")

    STATUS_LINK_BASE_URL: str = os.getenv("STATUS_LINK_BASE_URL", "http://localhost:8006")
    MATCH_TOKEN_TTL_HOURS: int = int(os.getenv("MATCH_TOKEN_TTL_HOURS", "168"))
    MAX_HEI_MATCH_ATTEMPTS: int = int(os.getenv("MAX_HEI_MATCH_ATTEMPTS", "5"))
    # Same object storage endpoint 9.Transparency Layer resolves media_objects
    # against - reused as-is to render the citizen's report photo inside the
    # broadcast brief (see app/brief.py). Full upload credentials (below)
    # are new - this service only ever read media_objects before; now it
    # also writes to it, for a university's uploaded solution PDF (see
    # app/object_storage.py / app/storage.py).
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "http://localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "sahyog")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "sahyog-dev-secret")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "false").lower() == "true"
    S3_BUCKET_DOCUMENTS: str = os.getenv("S3_BUCKET_DOCUMENTS", "sahyog-documents")
    BROADCAST_TOP_N: int = int(os.getenv("BROADCAST_TOP_N", "10"))

    INDUSTRY_PARTNERSHIP_BASE_URL: str = os.getenv("INDUSTRY_PARTNERSHIP_BASE_URL", "http://localhost:8007")
    LIFECYCLE_OUTCOME_BASE_URL: str = os.getenv("LIFECYCLE_OUTCOME_BASE_URL", "http://localhost:8008")
    TRANSPARENCY_BASE_URL: str = os.getenv("TRANSPARENCY_BASE_URL", "http://localhost:8009")

    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    ADMIN_FORM_PASSWORD: str = os.getenv("ADMIN_FORM_PASSWORD", "")

    EMAIL_DRY_RUN: bool = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"
    DEMO_HEI_NAME: str = os.getenv("DEMO_HEI_NAME", "Demo Institute of Technology")
    DEMO_HEI_CONTACT_EMAIL: str = os.getenv("DEMO_HEI_CONTACT_EMAIL", "demo-hei-inbox@example.com")

    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" or "pytest" in sys.modules


settings = Settings()

if not settings.INTERNAL_SERVICE_TOKEN and not settings.DEBUG:
    raise RuntimeError(
        "INTERNAL_SERVICE_TOKEN must be set (non-debug mode). Reuses the same "
        "repo-wide internal-services secret already configured for "
        "3.Triage and route <-> 5.ULB Dispatch."
    )
