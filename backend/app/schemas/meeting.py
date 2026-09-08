from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.meeting_status import MeetingStatus

class MeetingBase(BaseModel):
    title: str

class MeetingCreate(MeetingBase):
    pass

class MeetingResponse(MeetingBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: MeetingStatus
    created_at: datetime
    updated_at: datetime