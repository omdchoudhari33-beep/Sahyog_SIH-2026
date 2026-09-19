"""Object storage client (MinIO / any S3-compatible endpoint).

Two responsibilities:
  1. Upload bytes to the right bucket ("sahyog-documents" here - this
     service only ever uploads a university's solution PDF, never audio/
     images) and hand back a stable, fetchable URL.
  2. Register the upload in the shared `media_objects` registry table (see
     "3.Triage and route/schema_003_media_objects.sql" +
     "schema_005_proposal_documents.sql" here, which widens its media_type
     CHECK constraint to add 'document') so other services can find it by id.

Copied (not imported) from "5.ULB Dispatch/app/object_storage.py" - same
"each service stays independently deployable" idiom as the rest of this
repo - with media_type/bucket support narrowed to 'document' only, since
that's the only kind of file this service ever uploads.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger("object_storage")

_PUBLIC_READ_POLICY = (
    '{{"Version":"2012-10-17","Statement":[{{"Effect":"Allow",'
    '"Principal":"*","Action":"s3:GetObject",'
    '"Resource":"arn:aws:s3:::{bucket}/*"}}]}}'
)


@dataclass
class UploadedMedia:
    media_id: Optional[int]
    media_type: str
    bucket: str
    object_key: str
    url: str
    size_bytes: int


class ObjectStorage:
    """One instance per service, built from that service's own settings.
    Safe to construct even if MinIO isn't reachable yet at import time -
    bucket setup/uploads fail loudly at call time instead, same as any other
    outbound dependency in this repo (Bhashini, Ollama, SMTP)."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        use_ssl: bool = False,
        public_base_url: Optional[str] = None,
        bucket_documents: str = "sahyog-documents",
        database_url: Optional[str] = None,
        uploaded_by_service: str = "unknown",
    ) -> None:
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            use_ssl=use_ssl,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._public_base_url = (public_base_url or endpoint_url).rstrip("/")
        self._buckets = {"document": bucket_documents}
        self._database_url = database_url
        self._service_name = uploaded_by_service
        self._buckets_ready = False

    def _ensure_buckets(self) -> None:
        if self._buckets_ready:
            return
        for bucket in self._buckets.values():
            try:
                self._s3.head_bucket(Bucket=bucket)
            except ClientError:
                try:
                    self._s3.create_bucket(Bucket=bucket)
                except ClientError as exc:
                    logger.warning("could not create bucket %s: %s", bucket, exc)
                    continue
            # Public-read download policy - same hackathon-scope tradeoff
            # ULB Dispatch's copy of this file already documents: served
            # straight to the nodal-review admin UI by URL, no presigned
            # links implemented.
            try:
                self._s3.put_bucket_policy(Bucket=bucket, Policy=_PUBLIC_READ_POLICY.format(bucket=bucket))
            except ClientError:
                pass
        self._buckets_ready = True

    @staticmethod
    def build_object_key(prefix: str, filename: Optional[str], default_ext: str = "") -> str:
        ext = Path(filename or "").suffix or default_ext
        today = datetime.utcnow().strftime("%Y/%m/%d")
        return f"{prefix}/{today}/{uuid.uuid4().hex}{ext}"

    def upload(
        self,
        data: bytes,
        *,
        media_type: str,
        content_type: str,
        object_key: str,
        original_filename: Optional[str] = None,
    ) -> UploadedMedia:
        if media_type not in ("document",):
            raise ValueError("media_type must be 'document'")
        self._ensure_buckets()
        bucket = self._buckets[media_type]

        self._s3.put_object(Bucket=bucket, Key=object_key, Body=data, ContentType=content_type)
        url = f"{self._public_base_url}/{bucket}/{object_key}"

        media_id = self._register(
            media_type=media_type,
            bucket=bucket,
            object_key=object_key,
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=hashlib.sha256(data).hexdigest(),
            original_filename=original_filename,
        )
        return UploadedMedia(
            media_id=media_id, media_type=media_type, bucket=bucket,
            object_key=object_key, url=url, size_bytes=len(data),
        )

    def _register(self, **fields) -> Optional[int]:
        """Best-effort insert into media_objects. The upload above already
        succeeded either way - a registration failure (DB down, table not
        migrated yet) must never lose the fact that the file is safely in
        object storage, so this only logs and returns None."""
        if not self._database_url:
            return None
        try:
            import psycopg2

            dsn = self._database_url.replace("postgresql+psycopg2://", "postgresql://")
            conn = psycopg2.connect(dsn)
            try:
                with conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO media_objects
                            (media_type, bucket, object_key, content_type, size_bytes,
                             checksum_sha256, original_filename, uploaded_by_service)
                        VALUES (%(media_type)s, %(bucket)s, %(object_key)s, %(content_type)s,
                                %(size_bytes)s, %(checksum_sha256)s, %(original_filename)s,
                                %(uploaded_by_service)s)
                        RETURNING id
                        """,
                        {**fields, "uploaded_by_service": self._service_name},
                    )
                    row = cur.fetchone()
                    return row[0] if row else None
            finally:
                conn.close()
        except Exception:
            logger.warning("media_objects registration failed (file was still uploaded to object storage)", exc_info=True)
            return None
