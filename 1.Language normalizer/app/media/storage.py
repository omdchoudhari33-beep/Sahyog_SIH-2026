"""Module-level ObjectStorage singleton, built from this service's own
settings - same "one engine, built once, imported everywhere" idiom used
for Postgres engines elsewhere in this repo (e.g. "5.ULB Dispatch"/app/db.py)."""
from app.config import settings
from app.media.object_storage import ObjectStorage

storage = ObjectStorage(
    endpoint_url=settings.s3_endpoint_url,
    access_key=settings.s3_access_key,
    secret_key=settings.s3_secret_key,
    region=settings.s3_region,
    use_ssl=settings.s3_use_ssl,
    public_base_url=settings.s3_public_base_url,
    bucket_audio=settings.s3_bucket_audio,
    bucket_images=settings.s3_bucket_images,
    database_url=settings.database_url or None,
    uploaded_by_service="1.language_normalizer",
)
