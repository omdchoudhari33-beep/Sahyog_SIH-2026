from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ASRResult:
    transcript: str
    language: str | None
    confidence: float
