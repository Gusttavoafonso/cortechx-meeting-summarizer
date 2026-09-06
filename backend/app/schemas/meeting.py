from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeetingCreate(BaseModel):
    title: str


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
