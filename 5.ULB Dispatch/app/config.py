import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/dno_triage",
    )

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_ADDRESS: str = os.getenv("SMTP_FROM_ADDRESS", "")

    IMAP_HOST: str = os.getenv("IMAP_HOST", "")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER: str = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")
    IMAP_FOLDER: str = os.getenv("IMAP_FOLDER", "INBOX")

    STATUS_LINK_BASE_URL: str = os.getenv("STATUS_LINK_BASE_URL", "https://status.sahyog.example.gov.in")
    STATUS_LINK_TOKEN_TTL_HOURS: int = int(os.getenv("STATUS_LINK_TOKEN_TTL_HOURS", "720"))

    DISPATCH_MAX_RETRIES: int = int(os.getenv("DISPATCH_MAX_RETRIES", "3"))
    DISPATCH_RETRY_BACKOFF_SECONDS: int = int(os.getenv("DISPATCH_RETRY_BACKOFF_SECONDS", "300"))
    SLA_POLL_INTERVAL_SECONDS: int = int(os.getenv("SLA_POLL_INTERVAL_SECONDS", "900"))
    INBOX_POLL_INTERVAL_SECONDS: int = int(os.getenv("INBOX_POLL_INTERVAL_SECONDS", "300"))

    VISION_CLASSIFIER_URL: str = os.getenv("VISION_CLASSIFIER_URL", "")
    CLOSURE_GEO_RADIUS_METERS: float = float(os.getenv("CLOSURE_GEO_RADIUS_METERS", "150"))

    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    ADMIN_FORM_PASSWORD: str = os.getenv("ADMIN_FORM_PASSWORD", "")

    DISPATCH_EMAIL_LANGUAGE: str = os.getenv("DISPATCH_EMAIL_LANGUAGE", "en")
    MAX_CLOSURE_PHOTO_MB: int = int(os.getenv("MAX_CLOSURE_PHOTO_MB", "8"))

    # --- Hackathon fast-path defaults - see README "Hackathon fast-path" ---
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"
    DEMO_ULB_BOUNDARY_WKT: str = os.getenv(
        "DEMO_ULB_BOUNDARY_WKT",
        "POLYGON((85.0 22.5,86.5 22.5,86.5 24.0,85.0 24.0,85.0 22.5))",
    )
    DEMO_CONTACT_EMAIL: str = os.getenv("DEMO_CONTACT_EMAIL", "demo-ulb-inbox@example.com")
    EMAIL_DRY_RUN: bool = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
    RUN_BACKGROUND_LOOP_IN_PROCESS: bool = os.getenv("RUN_BACKGROUND_LOOP_IN_PROCESS", "true").lower() == "true"

    # Debug/test mode relaxes the "must have INTERNAL_SERVICE_TOKEN" startup
    # check below, so pytest can import app.main without a .env file.
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" or "pytest" in sys.modules


settings = Settings()

if not settings.INTERNAL_SERVICE_TOKEN and not settings.DEBUG:
    raise RuntimeError(
        "INTERNAL_SERVICE_TOKEN must be set (non-debug mode). "
        "Set it in .env - it must match the same value configured in "
        "3.Triage and route/.env for the dispatch webhook to authenticate."
    )
