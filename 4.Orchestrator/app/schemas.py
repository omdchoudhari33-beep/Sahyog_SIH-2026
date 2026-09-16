from typing import Any, Literal, Optional

from pydantic import BaseModel


class PipelineResult(BaseModel):
    request_id: str
    status: Literal["routed", "review_required", "geo_required", "failed"]
    stage: str
    detail: str
    agent1: Optional[dict[str, Any]] = None
    agent2: Optional[dict[str, Any]] = None
    agent3: Optional[dict[str, Any]] = None
