from __future__ import annotations

import base64
from typing import Optional

import httpx

from app.config import settings

INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

# Service IDs confirmed by calling this key's inference endpoint directly.
# The discovery endpoint (getModelsPipeline) that would normally look these
# up dynamically returned a degraded response (missing
# pipelineInferenceAPIEndPoint) after repeated use - likely rate-limited -
# so these are hardcoded instead of discovered per-request. IndicTrans2's
# "-all-" variant handles translation for every language below in either
# direction; TTS needs a family-specific model per language.
TRANSLATION_SERVICE_ID = "ai4bharat/indictrans-v2-all-gpu--t4"

# Individually verified against this project's key via the getModelsPipeline
# discovery endpoint (POST bhashini_config_url with
# {"pipelineTasks":[{"taskType":"tts","config":{"language":{"sourceLanguage":"<code>"}}}],
# "pipelineRequestConfig":{"pipelineId":...}}, Authorization header, same
# auth style as the inference endpoint - NOT the userID+ulcaApiKey pair).
# en/hi/bn/or all return a real serviceId; ur/ne/mai authoritatively return
# "No supported tasks found for this request!!" - TTS for those three is
# simply not provisioned on this pipeline, which is why an earlier version
# of this map (assuming the whole "indo_aryan" model family shared one
# working serviceId across all of hi/bn/or/ur/ne/mai) sent ur/ne/mai
# requests straight into a real 500 from Bhashini's own server every time.
# Translation (SUPPORTED_LANGUAGES below) is unaffected - ur/ne/mai text
# still translates fine, only the TTS step is unavailable for them.
TTS_SERVICE_IDS = {
    "en": "ai4bharat/indic-tts-coqui-misc-gpu--t4",
    "hi": "ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4",
    "bn": "ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4",
    "or": "ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4",
}

# Individually verified against this project's key via the getModelsPipeline
# discovery endpoint (same technique as TTS_SERVICE_IDS above). en/hi/bn/or/ur
# all return a real serviceId - ur's ASR genuinely works even though its TTS
# does not (see TTS_SERVICE_IDS - the two tasks are provisioned independently
# on this pipeline). ne/mai authoritatively return "No supported tasks found
# for this request!!" for ASR too, so they're left out entirely rather than
# listed with a serviceId that would just fail at call time - lang_code not
# in ASR_SERVICE_IDS is exactly the check app/media/pipeline.py's
# transcribe_with_cleanup() uses to raise UnsupportedAsrLanguageError
# up front instead of attempting a doomed API call. Santali ("sat") has no
# entry either and isn't in SUPPORTED_LANGUAGES at all - Bhashini has no
# ASR or translation model for it whatsoever.
ASR_SERVICE_IDS = {
    "en": "ai4bharat/whisper-medium-en--gpu--t4",
    "hi": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
    "bn": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
    "or": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
    "ur": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
}

# Whisper/ASR language names -> ISO codes Bhashini expects.
_LANGUAGE_CODES = {
    "english": "en", "en": "en",
    "hindi": "hi", "hi": "hi",
    "bengali": "bn", "bn": "bn",
    "santali": "sat", "sat": "sat",
    "odia": "or", "oriya": "or", "or": "or",
    "nepali": "ne", "ne": "ne",
    "maithili": "mai", "mai": "mai",
    "urdu": "ur", "ur": "ur",
}

# Verified against this Bhashini key. Mundari, Kurukh, Kharia, and Khortha
# are NOT covered by Bhashini at all (confirmed via the discovery endpoint -
# "sourceLanguage is not supported") - there is no fallback that fixes
# this, it's a scope limit of the platform itself, for any user's key.
SUPPORTED_LANGUAGES = {"hi", "bn", "or", "ne", "mai", "ur", "en"}


def is_language_supported(language: str | None) -> bool:
    """True if Bhashini can translate/synthesize speech for this language
    at all (ASR support is checked separately - see ASR_SERVICE_IDS).
    False for Santali ("sat") and anything else not in SUPPORTED_LANGUAGES -
    callers must treat that as "route to human review with the original
    text preserved", never guess/attempt processing anyway."""
    code = resolve_language_code(language)
    return code is None or code in SUPPORTED_LANGUAGES  # None == "no language given" == treat as English/passthrough


def resolve_language_code(language: str | None) -> str | None:
    if not language:
        return None
    key = language.strip().lower()
    if key in _LANGUAGE_CODES:
        return _LANGUAGE_CODES[key]
    # Already looks like an ISO 639 code (e.g. whisper.cpp's "hi", "bn").
    return key if len(key) <= 3 else None


def _headers() -> dict:
    return {"Authorization": settings.bhashini_ulca_api_key, "Content-Type": "application/json"}


# Module-level client so translate()/text_to_speech()/speech_to_text() reuse
# one keep-alive connection across calls instead of paying a new TCP+TLS
# handshake every request - each one-off httpx.post() was opening a fresh
# connection.
_client = httpx.Client()


def translate(
    text: str,
    source_language: str | None,
    target_language: str = "en",
) -> Optional[str]:
    """
    Translate text via the Bhashini NMT pipeline. Works in either direction
    (e.g. hi->en for an incoming report, en->hi for a spoken reply back to
    the citizen) - just swap source_language/target_language.

    Returns None on any failure (missing credentials, network error,
    unsupported language, unexpected response shape) so the caller can
    fall back to the original text - translation must never break the
    report pipeline.

    Bhashini expects native-script input (e.g. Devanagari for Hindi), not
    romanized transliteration - a romanized "gaddha" will not translate
    correctly even though the call succeeds.
    """
    if not text or not text.strip():
        return text
    if not settings.bhashini_ulca_api_key:
        return None

    source_code = resolve_language_code(source_language)
    if not source_code or source_code == target_language:
        return text
    if source_code not in SUPPORTED_LANGUAGES or target_language not in SUPPORTED_LANGUAGES:
        return None

    try:
        response = _client.post(
            INFERENCE_URL,
            headers=_headers(),
            json={
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": {
                            "language": {
                                "sourceLanguage": source_code,
                                "targetLanguage": target_language,
                            },
                            "serviceId": TRANSLATION_SERVICE_ID,
                        },
                    }
                ],
                "inputData": {"input": [{"source": text}]},
            },
            timeout=20.0,
        )
        response.raise_for_status()
        result = response.json()
        return result["pipelineResponse"][0]["output"][0]["target"]
    except Exception as exc:
        # Never break the pipeline over this, but a silent failure here is
        # what makes translation issues invisible - always log it.
        print(f"Bhashini translate() failed, falling back to passthrough: {exc}")
        return None


def speech_to_text(audio_bytes: bytes, language: str | None) -> Optional[str]:
    """
    Transcribe speech via Bhashini ASR - the only speech-to-text engine in
    this service (see app/agents/asr.py: the local Whisper implementation
    was removed, not kept as a fallback). Unlike the old Whisper path, this
    needs the spoken language known up front - no auto-detect - and
    Bhashini's response carries no confidence score, so a caller can't gate
    on transcription quality the way the Whisper path used to with its
    logprob-based estimate; a successful result is treated as trusted text.

    Expects 16kHz mono WAV bytes (matches what normalize_audio() in
    app/media/pipeline.py produces).

    Returns None on any failure (missing credentials, unsupported language,
    network error, unexpected response shape). The caller
    (transcribe_with_cleanup() in app/media/pipeline.py) turns a None here
    into a raised AsrFailedError - there is no local fallback, so a
    Bhashini outage means voice input is unavailable until it recovers.
    """
    if not audio_bytes:
        return None
    if not settings.bhashini_ulca_api_key:
        return None

    lang_code = resolve_language_code(language)
    service_id = ASR_SERVICE_IDS.get(lang_code) if lang_code else None
    if service_id is None:
        return None

    try:
        response = _client.post(
            INFERENCE_URL,
            headers=_headers(),
            json={
                "pipelineTasks": [
                    {
                        "taskType": "asr",
                        "config": {
                            "language": {"sourceLanguage": lang_code},
                            "serviceId": service_id,
                            "audioFormat": "wav",
                            "samplingRate": 16000,
                        },
                    }
                ],
                "inputData": {
                    "audio": [
                        {"audioContent": base64.b64encode(audio_bytes).decode("ascii")}
                    ]
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        return result["pipelineResponse"][0]["output"][0]["source"]
    except Exception as exc:
        # No local fallback exists any more - this failure surfaces to the
        # caller as AsrFailedError (502), it is not silently absorbed.
        print(f"Bhashini speech_to_text() failed: {exc}")
        return None


def text_to_speech(
    text: str,
    language: str | None,
    gender: str = "female",
) -> Optional[bytes]:
    """
    Synthesize speech via Bhashini TTS. Returns raw WAV audio bytes, or
    None on any failure / unsupported language - callers must treat
    speech as an optional overlay on the text response, never a
    requirement for the pipeline to function.
    """
    if not text or not text.strip():
        return None
    if not settings.bhashini_ulca_api_key:
        return None

    lang_code = resolve_language_code(language) or "en"
    service_id = TTS_SERVICE_IDS.get(lang_code)
    if service_id is None:
        return None

    try:
        response = _client.post(
            INFERENCE_URL,
            headers=_headers(),
            json={
                "pipelineTasks": [
                    {
                        "taskType": "tts",
                        "config": {
                            "language": {"sourceLanguage": lang_code},
                            "serviceId": service_id,
                            "gender": gender,
                        },
                    }
                ],
                "inputData": {"input": [{"source": text}]},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()
        audio_b64 = result["pipelineResponse"][0]["audio"][0]["audioContent"]
        return base64.b64decode(audio_b64)
    except Exception as exc:
        print(f"Bhashini text_to_speech() failed, no audio returned: {exc}")
        return None
