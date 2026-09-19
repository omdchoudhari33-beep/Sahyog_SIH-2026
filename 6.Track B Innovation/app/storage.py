"""Module-level ObjectStorage singleton, built from this service's own
settings - same "one engine, built once, imported everywhere" idiom as
app/db.py's `engine`."""
from app.config import settings
from app.object_storage import ObjectStorage

storage = ObjectStorage(
    endpoint_url=settings.S3_ENDPOINT_URL,
    access_key=settings.S3_ACCESS_KEY,
    secret_key=settings.S3_SECRET_KEY,
    region=settings.S3_REGION,
    use_ssl=settings.S3_USE_SSL,
    public_base_url=settings.S3_PUBLIC_BASE_URL,
    bucket_documents=settings.S3_BUCKET_DOCUMENTS,
    database_url=settings.DATABASE_URL,
    uploaded_by_service="6.track_b_innovation",
)
