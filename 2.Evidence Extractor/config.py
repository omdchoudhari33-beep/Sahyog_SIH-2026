"""Object storage settings get their own small Settings object here since
they're meant to point at the same MinIO instance the other services share
and need to be environment-specific. OLLAMA_BASE_URL lives here too now -
c1_text.py/c3_vision.py used to hardcode "http://localhost:11434", which
only ever worked when this service and Ollama ran on the same host; it
must be reachable at a different address (e.g. a Docker service name) in
any real deployment."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Comma-separated list of origins allowed to call this service from a
    # browser (CORS). Defaults to the local citizen-portal dev server.
    FRONTEND_ORIGINS: str = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "http://localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "sahyog")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "sahyog-dev-secret")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "false").lower() == "true"
    S3_BUCKET_AUDIO: str = os.getenv("S3_BUCKET_AUDIO", "sahyog-audio")
    S3_BUCKET_IMAGES: str = os.getenv("S3_BUCKET_IMAGES", "sahyog-images")

    # Optional. Same Postgres instance/DB as "3.Triage and route". Only used
    # to register each upload in the shared media_objects table (see
    # schema_003_media_objects.sql) - leave blank to skip the DB row and
    # still get durable object storage.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")


settings = Settings()
