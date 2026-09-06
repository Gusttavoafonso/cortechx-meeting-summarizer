from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.audio import AudioUploadResponse
from app.schemas.transcription import TranscriptResponse


class MeetingCreate(BaseModel):
    title: str


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    audio: AudioUploadResponse | None = None
    transcript: TranscriptResponse | None = None
