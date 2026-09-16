from __future__ import annotations

from pathlib import Path

from app.config import settings


def get_local_audio(path_value: str) -> Path:
    """Return a local audio file only if it is inside the configured local directory."""
    if not path_value:
        raise ValueError("local_audio_path is required")

    base = Path(settings.local_audio_dir).resolve()
    requested = Path(path_value).resolve()

    try:
        requested.relative_to(base)
    except ValueError as exc:
        raise PermissionError(
            f"Local audio path must be inside {base}"
        ) from exc

    if not requested.is_file():
        raise FileNotFoundError(f"Local audio file not found: {requested}")

    return requested
