from typing import Literal
from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    request_id: str = Field(min_length=1)
    input_type: Literal["text", "audio"]

    text: str | None = None
    media_url: str | None = None

    # Audio source (local only)
    local_audio_path: str | None = None

    source_language: str | None = None


class AgentResult(BaseModel):
    request_id: str
    status: Literal["completed", "review_required", "rejected"]
    input_type: Literal["text", "audio"]

    source_language: str | None = None
    standardized_text: str | None = None
    english_translation: str | None = None

    pii_scrubbed: bool = False
    review_status: Literal["not_required", "pending", "completed", "required"]
    asr_confidence: float | None = None