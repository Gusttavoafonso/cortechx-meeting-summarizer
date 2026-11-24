from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.meeting_status import MeetingStatus
from app.schemas.audio import AudioUploadResponse
from app.schemas.transcription import TranscriptResponse


class MeetingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class MeetingCreate(MeetingBase):
    @field_validator("title")
    @classmethod
    def validate_title_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("O título da reunião não pode ser vazio.")
        return clean


class MeetingSummaryPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    objective: str | None = None
    summary: str | None = None
    tasks_count: int = 0


class MeetingResponse(MeetingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: MeetingStatus
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    last_error: str | None = None
    audio: AudioUploadResponse | None = None
    transcript: TranscriptResponse | None = None
    summary: MeetingSummaryPreview | None = None


class MeetingStatsResponse(BaseModel):
    total_meetings: int
    completed_meetings: int
    processing_meetings: int
    failed_meetings: int
    total_audio_seconds: float
    total_tasks: int
    recent_meetings: list[MeetingResponse] = Field(default_factory=list)


class GlobalTaskItemResponse(BaseModel):
    id: int
    meeting_id: int
    meeting_title: str
    meeting_status: MeetingStatus
    description: str
    responsible: str | None = None
    deadline: date | None = None
    created_at: datetime


class MeetingProcessOptions(BaseModel):
    language: str | None = None
    provider: Literal["auto", "groq", "local"] | None = None
    auto_tasks: bool | None = None
    export_notion: bool | None = None
    integrations: list[str] | None = None
    skip_integrations: bool | None = None


class MeetingProcessResponse(BaseModel):
    meeting_id: int
    status: MeetingStatus = MeetingStatus.PROCESSING


class MeetingStatusResponse(BaseModel):
    meeting_id: int
    status: MeetingStatus
    updated_at: datetime
    last_error: str | None = None
