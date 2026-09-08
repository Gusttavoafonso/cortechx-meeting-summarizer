from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_session
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting import MeetingCreate, MeetingResponse
from app.services.meeting_service import MeetingService, MeetingNotFoundError

router = APIRouter(prefix = "/meetings", tags = ["meetings"])



def get_meeting_service(db: Session = Depends(get_session)) -> MeetingService:
    return MeetingService(MeetingRepository(db))


@router.post("/", response_model = MeetingResponse, status_code = status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate,
    service: MeetingService = Depends(get_meeting_service),
):
    return service.create(payload)

@router.get("/{meeting_id}", response_model = MeetingResponse)
def get_meeting(
    meeting_id: int,
    service: MeetingService = Depends(get_meeting_service),
):
    try:
        return service.get_by_id(meeting_id)
    except MeetingNotFoundError:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = f"Meeting not found.")

@router.get("/", response_model = list[MeetingResponse])
def list_meetings(
    service: MeetingService = Depends(get_meeting_service)
):
    return service.list_all()