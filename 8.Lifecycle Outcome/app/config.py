import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/dno_triage",
    )

    ULB_DISPATCH_BASE_URL: str = os.getenv("ULB_DISPATCH_BASE_URL", "http://localhost:8004")
    TRANSPARENCY_BASE_URL: str = os.getenv("TRANSPARENCY_BASE_URL", "http://localhost:8009")
    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    ADMIN_FORM_PASSWORD: str = os.getenv("ADMIN_FORM_PASSWORD", "")

    VISION_CLASSIFIER_URL: str = os.getenv("VISION_CLASSIFIER_URL", "")
    CLOSURE_GEO_RADIUS_METERS: float = float(os.getenv("CLOSURE_GEO_RADIUS_METERS", "150"))
    MAX_PILOT_PHOTO_MB: int = int(os.getenv("MAX_PILOT_PHOTO_MB", "8"))

    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" or "pytest" in sys.modules


settings = Settings()

if not settings.INTERNAL_SERVICE_TOKEN and not settings.DEBUG:
    raise RuntimeError(
        "INTERNAL_SERVICE_TOKEN must be set (non-debug mode). Reuses the same "
        "repo-wide internal-services secret already configured for the other services."
    )
