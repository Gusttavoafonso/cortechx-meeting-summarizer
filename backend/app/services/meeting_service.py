from datetime import datetime, timezone

from app.core.exceptions import MeetingNotFoundError
from app.models.meeting import Meeting
from app.models.meeting_status import VALID_TRANSITIONS, MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting import MeetingCreate


class InvalidMeetingTransitionError(ValueError):
    """A transição solicitada não é permitida."""


class MeetingService:
    def __init__(self, repository: MeetingRepository):
        self.repository = repository

    def create(self, data: MeetingCreate, user_id: int) -> Meeting:
        """Cria a reuniao ja vinculada ao usuario autenticado."""
        meeting = Meeting(
            title=data.title,
            status=MeetingStatus.RECEIVED,
            user_id=user_id,
        )
        return self.repository.create(meeting)

    def get_by_id(self, meeting_id: int, user_id: int) -> Meeting:
        """Busca a reuniao do usuario; levanta MeetingNotFoundError se for de outro."""
        meeting = self.repository.get_by_id(meeting_id, user_id)
        if meeting is None:
            raise MeetingNotFoundError(meeting_id)
        return meeting

    def list_all(self, user_id: int) -> list[Meeting]:
        """Lista somente as reunioes do usuario informado."""
        return self.repository.list_all(user_id)

    def get_for_pipeline(self, meeting_id: int) -> Meeting:
        """Busca sem filtro de posse, para o pipeline interno (ver repositorio)."""
        meeting = self.repository.get_for_pipeline(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(meeting_id)
        return meeting

    def update_status(
        self,
        meeting_id: int,
        new_status: MeetingStatus,
        *,
        error_message: str | None = None,
    ) -> Meeting:
        """Valida a transição, atualiza metadados e persiste o estado atomicamente.

        Chamada pelo pipeline interno e pelas rotas que ja validaram a posse,
        por isso busca a reunião sem filtro de usuário.
        """
        meeting = self.get_for_pipeline(meeting_id)
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
            if getattr(meeting, "processing_started_at", None) is None or current in {
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
