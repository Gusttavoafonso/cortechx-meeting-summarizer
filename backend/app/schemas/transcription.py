from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    speaker: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    text: str


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    meeting_id: int
    text: str = Field(
        validation_alias="content",
        description="Texto transcrito da reunião.",
    )
    content: str = Field(
        description="Conteúdo textual consolidado da transcrição.",
    )
    created_at: datetime
    segments: list[TranscriptSegmentResponse] = []
