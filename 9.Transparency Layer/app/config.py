import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/dno_triage",
    )

    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")

    # Same object storage endpoint every other service uses to turn a
    # media_objects (bucket, object_key) pair into a fetchable URL - see
    # "3.Triage and route/app/config.py"'s identical setting.
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "http://localhost:9000")

    # Comma-separated list of origins allowed to call this service from a
    # browser (CORS). Defaults to the local citizen-portal dev server.
    FRONTEND_ORIGINS: str = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" or "pytest" in sys.modules


settings = Settings()

if not settings.INTERNAL_SERVICE_TOKEN and not settings.DEBUG:
    raise RuntimeError(
        "INTERNAL_SERVICE_TOKEN must be set (non-debug mode). Reuses the same "
        "repo-wide internal-services secret already configured for the other services. "
        "Only gates POST /audit/log - the X1/X2 read endpoints are public by design."
    )
