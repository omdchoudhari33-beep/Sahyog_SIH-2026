import logging
import os
import uuid
from functools import partial
from typing import Optional
import anyio
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image

from config import settings

# Import our custom models and components
from schemas import (
    UnifiedEvidencePayload,
    Geolocation,
    MediaRef,
    StructuredEvidence,
    VisualEvidence,
    compute_requires_human_review,
)
from c1_text import extract_text_evidence
from c2_geo import resolve_geo_data
from c3_vision import audit_vision_evidence
from storage import storage

logger = logging.getLogger("evidence_extractor")


def _safe_temp_image_path(filename: Optional[str]) -> str:
    """Local pre-processing staging path for an uploaded photo, named with a
    UUID rather than the client-supplied filename verbatim. Two problems
    with the old `f"temp_uploads/{image.filename}"`: a browser/OS filename
    can contain path-traversal segments (`../..`) since nothing here
    constrains it, and it can contain characters this service's own debug
    prints then choke on - hit live as `UnicodeEncodeError: 'charmap' codec
    can't encode characters...` crashing the whole request with a 500 on
    Windows, where a redirected stdout defaults to cp1252, not UTF-8.
    Object storage already gets this right (see object_storage.py's
    `f"{prefix}/{today}/{uuid.uuid4().hex}{ext}"`) - this mirrors it for the
    local staging copy.
    """
    ext = os.path.splitext(filename or "")[1]
    if len(ext) > 10 or not ext.isascii():
        ext = ""  # discard anything that isn't a plausible plain extension
    return f"temp_uploads/{uuid.uuid4().hex}{ext}"


class PhotoEvidencePayload(BaseModel):
    report_id: str
    geolocation: Geolocation
    visual_evidence: VisualEvidence
    media: Optional[MediaRef] = None


def _persist_original_photo(raw: bytes, filename: Optional[str], geo: Geolocation) -> Optional[MediaRef]:
    """Uploads the ORIGINAL (pre-resize) photo bytes to object storage.
    Previously this service processed the citizen's photo entirely in
    memory/temp-disk and deleted it once classification finished - this is
    the first durable copy of a citizen's submitted evidence photo anywhere
    in the pipeline. Best-effort: a MinIO outage must not block evidence
    extraction, which has worked fine without persistence until now."""
    try:
        content_type = "image/png" if (filename or "").lower().endswith(".png") else "image/jpeg"
        object_key = storage.build_object_key("citizen-reports", filename, default_ext=".jpg")
        uploaded = storage.upload(
            raw,
            media_type="image",
            content_type=content_type,
            object_key=object_key,
            original_filename=filename,
            capture_lat=geo.latitude,
            capture_lon=geo.longitude,
        )
        return MediaRef(media_id=uploaded.media_id, bucket=uploaded.bucket, object_key=uploaded.object_key, url=uploaded.url)
    except Exception:
        logger.warning("object storage upload failed for evidence photo %s", filename, exc_info=True)
        return None

# Initialize the FastAPI server
app = FastAPI(title="Sahyog Subgraph C - Local Backend")
# Dev-only: lets the citizen-portal Next.js app (localhost:3000) call this
# service straight from the browser. Restricted to localhost dev ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure a temporary directory exists for uploads
os.makedirs("temp_uploads", exist_ok=True)

def resize_image_for_ai(image_path: str, max_size: int = 448):
    """
    Resizes the image to a max dimension (448px) for efficient vision-model input.
    LLaVA's CLIP vision encoder operates on ~336-448px internally regardless of
    input size, so anything above that only adds base64/JSON transfer overhead
    without improving analysis quality.
    Re-encodes as JPEG regardless of the original format: a base64-inlined PNG
    (the common phone-screenshot/some-camera-app case) is several times larger
    than an equivalent JPEG for a photo, which directly inflates the request
    body Ollama has to receive and parse before inference even starts.
    Must be run AFTER C2 has already extracted the EXIF data[cite: 1].
    """
    try:
        with Image.open(image_path) as img:
            img.thumbnail((max_size, max_size))
            img.convert("RGB").save(image_path, format="JPEG", quality=85)
    except Exception as e:
        print(f"Warning: Failed to resize image: {e}")

@app.post("/evidence/extract", response_model=UnifiedEvidencePayload)
async def extract_evidence(
    report_id: str = Form(...),
    raw_text: str = Form(...),
    image: Optional[UploadFile] = File(None),
    device_lat: Optional[float] = Form(None),
    device_lon: Optional[float] = Form(None),
    device_timestamp: Optional[str] = Form(None)
):
    print(f"\n--- New Citizen Report Received: {report_id} ---")
    
    image_path = None
    image_bytes = None

    # 1. Save the image unmodified first (Required for C2 EXIF extraction)[cite: 1]
    if image:
        image_bytes = await image.read()
        image_path = _safe_temp_image_path(image.filename)
        with open(image_path, "wb") as buffer:
            buffer.write(image_bytes)
        print(f"Saved original image to {image_path}")

    # 2. Run C1 (Text) concurrently with C2 (Geo) + image resize[cite: 1]
    # C2/resize don't depend on C1's output, and C1's Ollama call is the
    # slowest step (can take well over a minute on a cold model load) - so
    # overlap them instead of running four steps back-to-back. Everything
    # runs off the event loop so it doesn't freeze other requests (health
    # checks, concurrent submissions) for the duration.
    print("Running C1 Text AI + C2 Geo Extraction in parallel...")
    geo_result: Geolocation

    async def _run_c2_and_resize():
        nonlocal geo_result
        geo_result = await anyio.to_thread.run_sync(
            partial(
                resolve_geo_data,
                image_path=image_path,
                device_lat=device_lat,
                device_lon=device_lon,
                device_timestamp=device_timestamp,
            )
        )
        if image_path:
            # Resize after C2 has safely read the original EXIF[cite: 1]
            await anyio.to_thread.run_sync(resize_image_for_ai, image_path)

    text_result: StructuredEvidence
    async with anyio.create_task_group() as tg:

        async def _run_c1():
            nonlocal text_result
            text_result = await anyio.to_thread.run_sync(extract_text_evidence, raw_text)

        tg.start_soon(_run_c1)
        tg.start_soon(_run_c2_and_resize)

    # 3. Run C3 (Vision Processing)[cite: 1]
    vision_result = None
    if image_path:
        print("Running C3 Vision AI...")
        # C3 runs AFTER C1 because it needs the normalized_english text[cite: 1]
        vision_result = await anyio.to_thread.run_sync(
            audit_vision_evidence, image_path, text_result.normalized_english
        )

    # 5. Compute if a human needs to review this[cite: 1]
    print("Computing confidence gating...")
    needs_review = compute_requires_human_review(text_result, vision_result, geo_result)

    # 6. Persist the ORIGINAL (pre-resize) photo to object storage, then
    # clean up the temporary local copy[cite: 1]
    media = None
    if image_bytes is not None:
        media = await anyio.to_thread.run_sync(_persist_original_photo, image_bytes, image.filename, geo_result)
    if image_path and os.path.exists(image_path):
        os.remove(image_path)
        print("Cleaned up temporary image file.")

    # 7. Assemble the final unified payload[cite: 1]
    payload = UnifiedEvidencePayload(
        report_id=report_id,
        structured_evidence=text_result,
        geolocation=geo_result,
        visual_evidence=vision_result,
        requires_human_review=needs_review,
        media=media,
    )

    print("--- Processing Complete ---\n")
    return payload


@app.post("/evidence/attach-photo", response_model=PhotoEvidencePayload)
async def attach_photo(
    report_id: str = Form(...),
    normalized_english: str = Form(...),
    image: UploadFile = File(...),
    device_lat: Optional[float] = Form(None),
    device_lon: Optional[float] = Form(None),
    device_timestamp: Optional[str] = Form(None),
):
    """
    Runs C2 (geo) + C3 (vision) against an ALREADY-classified report from
    /evidence/extract. Used by the conversational flow's photo step so
    attaching a photo doesn't re-run the (slow) C1 text classification.
    """
    print(f"\n--- Photo attached to report: {report_id} ---")

    image_bytes = await image.read()
    image_path = _safe_temp_image_path(image.filename)
    with open(image_path, "wb") as buffer:
        buffer.write(image_bytes)
    print(f"Saved original image to {image_path}")

    print("Running C2 Geo Extraction...")
    geo_result = await anyio.to_thread.run_sync(
        partial(
            resolve_geo_data,
            image_path=image_path,
            device_lat=device_lat,
            device_lon=device_lon,
            device_timestamp=device_timestamp,
        )
    )

    print("Resizing image for LLaVA AI...")
    await anyio.to_thread.run_sync(resize_image_for_ai, image_path)

    print("Running C3 Vision AI...")
    vision_result = await anyio.to_thread.run_sync(
        audit_vision_evidence, image_path, normalized_english
    )

    media = await anyio.to_thread.run_sync(_persist_original_photo, image_bytes, image.filename, geo_result)

    if os.path.exists(image_path):
        os.remove(image_path)
        print("Cleaned up temporary image file.")

    print("--- Photo Processing Complete ---\n")
    return PhotoEvidencePayload(
        report_id=report_id,
        geolocation=geo_result,
        visual_evidence=vision_result,
        media=media,
    )