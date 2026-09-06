from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    speaker: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    text: str


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    content: str
    created_at: datetime
    segments: list[TranscriptSegmentResponse] = []
