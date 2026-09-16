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

    STATUS_LINK_BASE_URL: str = os.getenv("STATUS_LINK_BASE_URL", "http://localhost:8007")
    MATCH_TOKEN_TTL_HOURS: int = int(os.getenv("MATCH_TOKEN_TTL_HOURS", "168"))

    LIFECYCLE_OUTCOME_BASE_URL: str = os.getenv("LIFECYCLE_OUTCOME_BASE_URL", "http://localhost:8008")
    TRANSPARENCY_BASE_URL: str = os.getenv("TRANSPARENCY_BASE_URL", "http://localhost:8009")

    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    ADMIN_FORM_PASSWORD: str = os.getenv("ADMIN_FORM_PASSWORD", "")

    EMAIL_DRY_RUN: bool = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"
    DEMO_PARTNER_NAME: str = os.getenv("DEMO_PARTNER_NAME", "Demo Industry Partner Pvt Ltd")
    DEMO_PARTNER_CONTACT_EMAIL: str = os.getenv("DEMO_PARTNER_CONTACT_EMAIL", "demo-partner-inbox@example.com")

    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" or "pytest" in sys.modules


settings = Settings()

if not settings.INTERNAL_SERVICE_TOKEN and not settings.DEBUG:
    raise RuntimeError(
        "INTERNAL_SERVICE_TOKEN must be set (non-debug mode). Reuses the same "
        "repo-wide internal-services secret already configured for the other services."
    )
