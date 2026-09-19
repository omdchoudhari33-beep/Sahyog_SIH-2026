import json
import logging
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
from app.media.storage import storage
from app.services import bhashini


router = APIRouter()
logger = logging.getLogger(__name__)


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
    original_text = payload.text
    text = payload.text

    if target_language == "sat":
        # Bhashini has no Santali model at all - use the self-hosted
        # translate+TTS fallback instead (see app/services/santali_local.py).
        # Same "fall back to English rather than staying silent" contract
        # as the Bhashini path below on any failure.
        from app.services import santali_local

        try:
            with _Stage("speak: santali local translate"):
                santali_text = await anyio.to_thread.run_sync(
                    santali_local.translate_english_to_santali, text
                )
            with _Stage("speak: santali local tts"):
                audio_bytes = await anyio.to_thread.run_sync(
                    santali_local.synthesize_speech_via_local_model, santali_text
                )
            return Response(content=audio_bytes, media_type="audio/wav")
        except santali_local.SantaliLocalError:
            logger.warning("Santali local speak failed, falling back to English TTS", exc_info=True)
            target_language = "en"

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

    if target_language == "ur":
        # Bhashini's TTS genuinely isn't provisioned for Urdu (confirmed
        # via its discovery endpoint - see bhashini.py's TTS_SERVICE_IDS
        # comment), but the same self-hosted Indic Parler-TTS model
        # already running for Santali lists Urdu as a supported language
        # too - try that before giving up to English. `text` here is
        # already the Bhashini-translated Urdu text from above.
        from app.services import santali_local

        try:
            with _Stage("speak: urdu local tts"):
                audio_bytes = await anyio.to_thread.run_sync(
                    santali_local.synthesize_speech_via_local_model, text
                )
            return Response(content=audio_bytes, media_type="audio/wav")
        except santali_local.SantaliLocalError:
            logger.warning("Urdu local TTS fallback failed, falling back to English TTS", exc_info=True)
            target_language = "en"
            text = original_text

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

    Also persists the recording durably to object storage (see
    app/media/storage.py). The local_audio_dir copy is a working file for
    ffmpeg/faster-whisper, not the system of record - previously it was the
    ONLY copy, and got silently lost the moment tmp cleanup ran, meaning a
    citizen's or officer's only durable record of the original audio never
    existed at all.
    """
    upload_dir = Path(settings.local_audio_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    raw = await file.read()
    suffix = Path(file.filename or "audio").suffix or ".webm"
    destination = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    destination.write_bytes(raw)

    media_id = None
    media_url = None
    try:
        uploaded = storage.upload(
            raw,
            media_type="audio",
            content_type=file.content_type or "application/octet-stream",
            object_key=storage.build_object_key("citizen-reports", file.filename, default_ext=suffix),
            original_filename=file.filename,
        )
        media_id, media_url = uploaded.media_id, uploaded.url
    except Exception:
        # Object storage is a durability upgrade, not a hard requirement of
        # this endpoint's existing contract (local_audio_path) - a MinIO
        # outage must never block a citizen from filing a report.
        logger.warning("object storage upload failed for %s", destination, exc_info=True)

    return {
        "local_audio_path": str(destination.resolve()),
        "media_id": media_id,
        "media_url": media_url,
    }


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

    # A language with no translation model anywhere (Bhashini OR the local
    # Santali fallback below) must never silently fall through
    # translate_to_english()'s safe-fallback-on-transient-failure path,
    # which would return the ORIGINAL untranslated script mislabeled as
    # "english_translation" - the citizen's actual words are preserved
    # here either way, just honestly flagged for a human to read/translate
    # instead of guessed at by an LLM that almost certainly can't read
    # this script. Santali ("sat") is NOT unsupported any more - Bhashini
    # itself has no model for it, but app/services/santali_local.py does
    # (see translate_to_english(), called unconditionally below), so it
    # must fall through to the real translation attempt instead of being
    # caught by this Bhashini-only check.
    if (
        bhashini.resolve_language_code(payload.source_language) != "sat"
        and not bhashini.is_language_supported(payload.source_language)
    ):
        return AgentResult(
            request_id=payload.request_id,
            status="review_required",
            input_type=payload.input_type,
            source_language=payload.source_language,
            standardized_text=standardized,
            english_translation=None,
            pii_scrubbed=True,
            review_status="required",
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
