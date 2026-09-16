"""
One-time generator for the "filler" voice clip played the instant a citizen
stops recording, while the real pipeline (ASR + Ollama classification, ~30s)
is still running - it masks perceived latency, it doesn't reduce the real
processing time. Run this whenever the filler script text changes or a new
language is added; it is NOT called at request time.

Uses this service's own Bhashini translate()/text_to_speech() so the clips
go through the exact same pipeline (and quality) as live replies, instead of
hand-written per-language translations.

Usage (from this directory, with .env / the venv already set up):
    python scripts/generate_filler_audio.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import bhashini  # noqa: E402

FILLER_TEXT_EN = (
    "Thank you for reaching out. My name is Maya, and I will help you "
    "register your complaint."
)

# Same language set as ASR_SERVICE_IDS/TTS_SERVICE_IDS - Santali has no
# Bhashini TTS coverage on this key, so it's skipped rather than producing a
# broken/empty clip.
LANGUAGES = ["en", "hi", "bn", "or", "ur", "ne", "mai"]

OUTPUT_DIR = (
    Path(__file__).resolve().parents[2] / "4.Orchestrator" / "static" / "audio"
)


def generate() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for lang in LANGUAGES:
        print(f"[{lang}] translating...")
        text = FILLER_TEXT_EN
        if lang != "en":
            translated = bhashini.translate(FILLER_TEXT_EN, "en", lang)
            if not translated:
                print(f"[{lang}] translate() failed - skipping")
                failures.append(lang)
                continue
            text = translated

        print(f"[{lang}] synthesizing: {text}")
        audio_bytes = bhashini.text_to_speech(text, lang)
        if not audio_bytes:
            print(f"[{lang}] text_to_speech() failed - skipping")
            failures.append(lang)
            continue

        out_path = OUTPUT_DIR / f"filler_{lang}.wav"
        out_path.write_bytes(audio_bytes)
        print(f"[{lang}] wrote {out_path} ({len(audio_bytes)} bytes)")

    print()
    if failures:
        print(f"Done with failures for: {', '.join(failures)} - re-run to retry them.")
    else:
        print("Done - all languages generated.")


if __name__ == "__main__":
    generate()
