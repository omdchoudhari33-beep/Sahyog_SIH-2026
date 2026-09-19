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

    # Object storage (MinIO / any S3-compatible endpoint) - pilot validation
    # photos are uploaded here instead of the local "pilot_uploads/" disk
    # folder. See app/object_storage.py and
    # "3.Triage and route/schema_003_media_objects.sql".
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "http://localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "sahyog")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "sahyog-dev-secret")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "false").lower() == "true"
    S3_BUCKET_AUDIO: str = os.getenv("S3_BUCKET_AUDIO", "sahyog-audio")
    S3_BUCKET_IMAGES: str = os.getenv("S3_BUCKET_IMAGES", "sahyog-images")

    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" or "pytest" in sys.modules


settings = Settings()

if not settings.INTERNAL_SERVICE_TOKEN and not settings.DEBUG:
    raise RuntimeError(
        "INTERNAL_SERVICE_TOKEN must be set (non-debug mode). Reuses the same "
        "repo-wide internal-services secret already configured for the other services."
    )
