from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.agents.asr import ASRResult
from app.services import bhashini


class AudioPipelineError(RuntimeError):
    pass


class UnsupportedAsrLanguageError(AudioPipelineError):
    pass


class AsrFailedError(AudioPipelineError):
    pass


def normalize_audio(input_path: Path | str) -> Path:
    """Convert arbitrary supported audio to 16 kHz mono PCM WAV."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    ffmpeg_setting = settings.ffmpeg_executable
    if Path(ffmpeg_setting).is_absolute():
        ffmpeg = Path(ffmpeg_setting)
        if not ffmpeg.exists():
            raise FileNotFoundError(
                f"FFmpeg executable not found: {ffmpeg}"
            )
        ffmpeg_command = str(ffmpeg)
    else:
        ffmpeg_command = shutil.which(ffmpeg_setting)
        if not ffmpeg_command:
            raise FileNotFoundError(
                f"FFmpeg executable '{ffmpeg_setting}' was not found on PATH"
            )

    temp_dir = Path(settings.temp_audio_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    fd, output_name = tempfile.mkstemp(
        prefix="normalized_",
        suffix=".wav",
        dir=temp_dir,
    )
    os.close(fd)

    output = Path(output_name)

    command = [
        ffmpeg_command,
        "-y",
        "-i", str(input_path),
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(output),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        output.unlink(missing_ok=True)
        raise AudioPipelineError(
            "FFmpeg normalization failed:\n"
            f"{result.stderr.strip()}"
        )

    return output


def transcribe_with_cleanup(
    input_path: Path | str, source_language: str | None = None
) -> ASRResult:
    """
    Bhashini ASR is the primary speech-to-text engine, except for Santali
    ("sat") - Bhashini has no model for it at all, so that one language is
    routed to a self-hosted alternative instead (see
    app/services/santali_local.py). Any other language Bhashini doesn't
    cover (see ASR_SERVICE_IDS) or a failed Bhashini call means this
    raises instead of transcribing, so callers must treat audio input as
    unavailable rather than silently degraded when that happens.
    """
    input_path = Path(input_path)
    normalized = None
    try:
        normalized = normalize_audio(input_path)
        wav_bytes = normalized.read_bytes()

        lang_code = bhashini.resolve_language_code(source_language)

        if lang_code == "sat":
            from app.services import santali_local

            try:
                transcript, confidence = santali_local.transcribe_santali(wav_bytes)
            except santali_local.SantaliLocalError as exc:
                raise AsrFailedError(str(exc)) from exc
            return ASRResult(transcript=transcript, language="sat", confidence=confidence)

        if lang_code not in bhashini.ASR_SERVICE_IDS:
            raise UnsupportedAsrLanguageError(
                f"Bhashini ASR does not support language '{source_language}' "
                f"(resolved: '{lang_code}')"
            )

        transcript = bhashini.speech_to_text(wav_bytes, lang_code)
        if transcript is None:
            raise AsrFailedError("Bhashini speech_to_text() failed - see agent1 logs")

        # Bhashini gives no confidence score; treat a successful result as
        # trusted (there's no local estimate to fall back on any more).
        return ASRResult(transcript=transcript, language=lang_code, confidence=1.0)
    finally:
        if normalized:
            normalized.unlink(missing_ok=True)
