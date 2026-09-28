from app.models.meeting_status import MeetingStatus
from app.models.meeting import Meeting
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting import MeetingCreate

class MeetingNotFoundError(Exception):
    """Levantada quando uma meeting não é encontrada."""

class MeetingService:
    def __init__(self, repository: MeetingRepository):
        self.repository = repository

    def create(self, data: MeetingCreate) -> Meeting:
        meeting = Meeting(title = data.title, status = MeetingStatus.RECEIVED)
        return self.repository.create(meeting)

    def get_by_id(self, meeting_id: int) -> Meeting:
        meeting = self.repository.get_by_id(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(meeting_id)
        return meeting

    def list_all(self) -> list[Meeting]:
        return self.repository.list_all()