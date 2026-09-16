import json
import time
import uuid
from pathlib import Path

import anyio
from fastapi import APIRouter, File, Header, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.schemas import IncomingMessage, AgentResult
from app.security.signature import verify_signature
from app.agents.pii_scrubber import scrub_pii
from app.agents.normalizer import normalize_text
from app.agents.translator import translate_to_english
from app.media.local import get_local_audio
from app.media.pipeline import (
    AsrFailedError,
    UnsupportedAsrLanguageError,
    transcribe_with_cleanup,
)
from app.services import bhashini


router = APIRouter()


class _Stage:
    """Times one sub-step and prints it, so the orchestrator's coarse
    per-agent timing can be broken down further (e.g. is the ASR pass or
    the Bhashini network call the bigger cost inside "agent1 webhook")."""

    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        print(f"[timing]   agent1: {self.label}: {time.perf_counter() - self._start:.2f}s")


class SpeakRequest(BaseModel):
    text: str
    language: str | None = "en"


@router.post("/speak")
async def speak(payload: SpeakRequest):
    """
    Turns a system message into spoken audio so the conversational flow can
    talk back to the citizen in their own language, not just show text.

    Speech is always optional: if Bhashini can't translate/synthesize for
    this language (unsupported, or unreachable), returns 204 with no body
    rather than an error - callers must fall back to text-only silently.
    """
    target_language = bhashini.resolve_language_code(payload.language) or "en"
    text = payload.text

    if target_language != "en":
        with _Stage("speak: bhashini translate"):
            translated = await anyio.to_thread.run_sync(
                bhashini.translate, text, "en", target_language
            )
        if translated:
            text = translated
        else:
            # Couldn't translate into this language - speaking English is
            # still more useful than staying silent.
            target_language = "en"

    with _Stage("speak: bhashini tts"):
        audio_bytes = await anyio.to_thread.run_sync(
            bhashini.text_to_speech, text, target_language
        )
    if audio_bytes is None:
        return Response(status_code=204)

    return Response(content=audio_bytes, media_type="audio/wav")


@router.post("/audio/upload")
async def upload_audio(file: UploadFile = File(...)):
    """
    Internal-only endpoint (localhost, no auth) so a caller that only has
    audio bytes - a browser recording, an orchestrator relaying an upload -
    can hand them off and get back a local_audio_path usable with /webhook.
    """
    upload_dir = Path(settings.local_audio_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "audio").suffix or ".webm"
    destination = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    destination.write_bytes(await file.read())

    return {"local_audio_path": str(destination.resolve())}


@router.post("/webhook", response_model=AgentResult)
async def receive_message(
    request: Request,
    x_signature: str | None = Header(default=None),
):
    """
    Internal application webhook.

    This preserves the existing HMAC contract:
    X-Signature = HMAC-SHA256(raw_body, WEBHOOK_SECRET)
    """
    raw_body = await request.body()

    if not x_signature or not verify_signature(
        raw_body,
        x_signature,
        settings.webhook_secret,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    payload = IncomingMessage.model_validate(
        json.loads(raw_body)
    )

    if payload.input_type == "audio":
        return await process_audio_message(payload)

    if not payload.text:
        raise HTTPException(
            status_code=422,
            detail="Text is required for text input",
        )

    scrubbed = scrub_pii(payload.text)
    standardized = normalize_text(
        scrubbed,
        payload.source_language,
    )
    # Blocking network call (Bhashini) - run off the event loop so it
    # can't stall other requests (health checks, concurrent submissions).
    translated = await anyio.to_thread.run_sync(
        translate_to_english, standardized, payload.source_language
    )

    return AgentResult(
        request_id=payload.request_id,
        status="completed",
        input_type=payload.input_type,
        source_language=payload.source_language,
        standardized_text=standardized,
        english_translation=translated,
        pii_scrubbed=True,
        review_status="not_required",
    )


async def process_audio_message(
    payload: IncomingMessage,
) -> AgentResult:
    """
    Process a local audio file.
    """

    if not payload.local_audio_path:
        raise HTTPException(
            status_code=422,
            detail="Audio requires local_audio_path",
        )

    audio_path = get_local_audio(payload.local_audio_path)

    # Bhashini ASR is the only speech-to-text engine (no local fallback) -
    # run off the event loop so it doesn't freeze other requests (health
    # checks included) for the duration.
    try:
        with _Stage("webhook: ASR (bhashini)"):
            asr = await anyio.to_thread.run_sync(
                transcribe_with_cleanup, audio_path, payload.source_language
            )
    except UnsupportedAsrLanguageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AsrFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if asr.confidence < settings.asr_confidence_threshold:
        return AgentResult(
            request_id=payload.request_id,
            status="review_required",
            input_type="audio",
            source_language=asr.language,
            standardized_text=asr.transcript,
            english_translation=None,
            pii_scrubbed=False,
            review_status="required",
            asr_confidence=asr.confidence,
        )

    scrubbed = scrub_pii(asr.transcript)

    standardized = normalize_text(
        scrubbed,
        asr.language,
    )

    with _Stage("webhook: bhashini translate to english"):
        translated = await anyio.to_thread.run_sync(
            translate_to_english, standardized, asr.language
        )

    return AgentResult(
        request_id=payload.request_id,
        status="completed",
        input_type="audio",
        source_language=asr.language,
        standardized_text=standardized,
        english_translation=translated,
        pii_scrubbed=True,
        review_status="not_required",
        asr_confidence=asr.confidence,
    )
