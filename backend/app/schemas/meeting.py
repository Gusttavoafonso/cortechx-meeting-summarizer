from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.audio import AudioUploadResponse
from app.schemas.transcription import TranscriptResponse


class MeetingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("O título da reunião não pode ser vazio.")
        return clean


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    audio: AudioUploadResponse | None = None
    transcript: TranscriptResponse | None = None
