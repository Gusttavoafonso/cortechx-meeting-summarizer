from datetime import datetime, timezone

from app.models.meeting_status import MeetingStatus, VALID_TRANSITIONS
from app.models.meeting import Meeting
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting import MeetingCreate


class MeetingNotFoundError(Exception):
    """Levantada quando uma meeting não é encontrada."""


class InvalidMeetingTransitionError(ValueError):
    """A transição solicitada não é permitida."""


class MeetingService:
    def __init__(self, repository: MeetingRepository):
        self.repository = repository

    def create(self, data: MeetingCreate) -> Meeting:
        meeting = Meeting(title=data.title, status=MeetingStatus.RECEIVED)
        return self.repository.create(meeting)

    def get_by_id(self, meeting_id: int) -> Meeting:
        meeting = self.repository.get_by_id(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(meeting_id)
        return meeting

    def list_all(self) -> list[Meeting]:
        return self.repository.list_all()

    def update_status(
        self,
        meeting_id: int,
        new_status: MeetingStatus,
        *,
        error_message: str | None = None,
    ) -> Meeting:
        """Valida a transição, atualiza metadados e persiste o estado atomicamente."""
        meeting = self.get_by_id(meeting_id)
        current = MeetingStatus(meeting.status)
        target = MeetingStatus(new_status)

        if current != target and target not in VALID_TRANSITIONS.get(current, set()):
            raise InvalidMeetingTransitionError(
                f"Transição de estado inválida: {current.value} -> {target.value}"
            )

        now = datetime.now(timezone.utc)
        meeting.status = target
        meeting.updated_at = now

        if target in {MeetingStatus.TRANSCRIBING, MeetingStatus.PROCESSING}:
            if meeting.processing_started_at is None or current in {
                MeetingStatus.COMPLETED,
                MeetingStatus.FAILED,
                MeetingStatus.TRANSCRIBED,
                MeetingStatus.AUDIO_UPLOADED,
            }:
                meeting.processing_started_at = now
            meeting.processing_completed_at = None
            meeting.last_error = None

        if target == MeetingStatus.COMPLETED:
            meeting.processing_completed_at = now
            meeting.last_error = None
        elif target == MeetingStatus.FAILED:
            meeting.processing_completed_at = now
            meeting.last_error = (error_message or "Falha não especificada")[:2000]
        elif error_message is None and target != MeetingStatus.FAILED:
            meeting.last_error = None

        return self.repository.update_status(meeting, status=target)
