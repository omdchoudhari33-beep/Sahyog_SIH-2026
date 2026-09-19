"""Client for the self-hosted Santali ASR/translation/TTS service.

Bhashini has no Santali ("sat") model at all for any of these three tasks
(confirmed live against its own getModelsPipeline discovery endpoint - see
app/services/bhashini.py's comments), so this one language is routed to
open checkpoints (Meta's MMS for ASR, AI4Bharat's IndicTrans2 for
translation, AI4Bharat's Indic Parler-TTS for speech) instead. Those
libraries (torch/transformers) fail to load natively on this machine's
Windows install - Smart App Control blocks their DLLs - so they run in a
small containerized service instead (santali-voice-service/, started via
the repo's docker-compose.yml alongside Postgres/MinIO) and this module
just talks HTTP to it, the same "native app service, containerized infra
dependency" split every other service already uses for Postgres.

The TTS model (Indic Parler-TTS) isn't Santali-only - its own model card
lists Urdu as a supported language too, and Bhashini's TTS genuinely
isn't provisioned for Urdu either (same discovery-endpoint check, see
bhashini.py's TTS_SERVICE_IDS comment) - so synthesize_speech_via_local_model()
below is also used as Urdu's spoken-reply fallback in webhook.py's
/speak, not just Santali's.
"""
from __future__ import annotations

import httpx

from app.config import settings


class SantaliLocalError(RuntimeError):
    """Raised when the santali-voice-service call fails (unreachable,
    still downloading its models, or an inference error) - callers must
    treat this the same as any other ASR/translation/TTS failure (fall
    back to text/human review), never let it crash the request."""


def transcribe_santali(wav_bytes: bytes) -> tuple[str, float]:
    """wav_bytes must already be 16kHz mono PCM WAV (see
    app/media/pipeline.py's normalize_audio - the same file every other
    language's ASR call already uses). Returns (transcript, confidence).

    timeout is generous (see synthesize_speech_via_local_model's comment
    for the same reasoning) - a real citizen recording live-tested at
    120.75s and got a 502 from this timing out at the old 120.0s value,
    even though the container was still working, not stuck; this is
    worse under concurrent load (e.g. another request already using the
    container's single GPU queue)."""
    try:
        response = httpx.post(
            f"{settings.santali_voice_service_url}/asr",
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            timeout=300.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["transcript"], data["confidence"]
    except Exception as exc:
        raise SantaliLocalError(f"Santali ASR failed: {exc}") from exc


def _translate(text: str, source: str, target: str) -> str:
    response = httpx.post(
        f"{settings.santali_voice_service_url}/translate",
        json={"text": text, "source": source, "target": target},
        timeout=300.0,
    )
    response.raise_for_status()
    return response.json()["text"]


def translate_santali_to_english(text: str) -> str:
    try:
        return _translate(text, "sat", "en")
    except Exception as exc:
        raise SantaliLocalError(f"Santali->English translation failed: {exc}") from exc


def translate_english_to_santali(text: str) -> str:
    try:
        return _translate(text, "en", "sat")
    except Exception as exc:
        raise SantaliLocalError(f"English->Santali translation failed: {exc}") from exc


def synthesize_speech_via_local_model(text: str) -> bytes:
    """Returns WAV bytes, same contract as bhashini.text_to_speech(). The
    underlying model auto-detects the language from the text itself (no
    language param to pass) - used for both Santali and Urdu replies.

    Autoregressive generation time scales with sentence length - a short
    test string finishes in seconds, but a full reply sentence genuinely
    took long enough to exceed an earlier 120s timeout here even though
    the container's own log showed a completed 200 (confirmed live: the
    client gave up before the model finished, not a real failure)."""
    try:
        response = httpx.post(
            f"{settings.santali_voice_service_url}/tts",
            json={"text": text},
            timeout=300.0,
        )
        response.raise_for_status()
        return response.content
    except Exception as exc:
        raise SantaliLocalError(f"Local TTS failed: {exc}") from exc
