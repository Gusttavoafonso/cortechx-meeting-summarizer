from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AudioUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    meeting_id: int
    filename: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    file_path: str
    uploaded_at: datetime = Field(validation_alias="created_at")

