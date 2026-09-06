from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AudioUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: int
    filename: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    file_path: str
    uploaded_at: datetime
