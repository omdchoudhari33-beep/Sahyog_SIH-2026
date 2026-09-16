import os
import shutil
from functools import partial
from typing import Optional
import anyio
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from PIL import Image

# Import our custom models and components
from schemas import (
    UnifiedEvidencePayload,
    Geolocation,
    StructuredEvidence,
    VisualEvidence,
    compute_requires_human_review,
)
from c1_text import extract_text_evidence
from c2_geo import resolve_geo_data
from c3_vision import audit_vision_evidence


class PhotoEvidencePayload(BaseModel):
    report_id: str
    geolocation: Geolocation
    visual_evidence: VisualEvidence

# Initialize the FastAPI server
app = FastAPI(title="Sahyog Subgraph C - Local Backend")

# Ensure a temporary directory exists for uploads
os.makedirs("temp_uploads", exist_ok=True)

def resize_image_for_ai(image_path: str, max_size: int = 512):
    """
    Resizes the image to a max dimension (512px) for efficient vision-model input.
    LLaVA's CLIP vision encoder operates on ~336-448px internally regardless of
    input size, so anything above that only adds base64/JSON transfer overhead
    without improving analysis quality.
    Must be run AFTER C2 has already extracted the EXIF data[cite: 1].
    """
    try:
        with Image.open(image_path) as img:
            img.thumbnail((max_size, max_size))
            img.save(image_path)
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
    
    # 1. Save the image unmodified first (Required for C2 EXIF extraction)[cite: 1]
    if image:
        image_path = f"temp_uploads/{image.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
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

    # 6. Cleanup the temporary image file[cite: 1]
    if image_path and os.path.exists(image_path):
        os.remove(image_path)
        print("Cleaned up temporary image file.")

    # 7. Assemble the final unified payload[cite: 1]
    payload = UnifiedEvidencePayload(
        report_id=report_id,
        structured_evidence=text_result,
        geolocation=geo_result,
        visual_evidence=vision_result,
        requires_human_review=needs_review
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

    image_path = f"temp_uploads/{image.filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    print(f"Saved original image to {image_path}")

    print("Running C2 Geo Extraction...")
    geo_result = resolve_geo_data(
        image_path=image_path,
        device_lat=device_lat,
        device_lon=device_lon,
        device_timestamp=device_timestamp,
    )

    print("Resizing image for LLaVA AI...")
    resize_image_for_ai(image_path)

    print("Running C3 Vision AI...")
    vision_result = await anyio.to_thread.run_sync(
        audit_vision_evidence, image_path, normalized_english
    )

    if os.path.exists(image_path):
        os.remove(image_path)
        print("Cleaned up temporary image file.")

    print("--- Photo Processing Complete ---\n")
    return PhotoEvidencePayload(
        report_id=report_id,
        geolocation=geo_result,
        visual_evidence=vision_result,
    )