from app.core.config import settings
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.summary import SummaryResponse
from app.services.summarization.service import SummarizationService
from app.services.integrations.service import IntegrationService
import logging

logger = logging.getLogger(__name__)

class MeetingNotFoundError(Exception):
    """A reunião informada não existe."""

class TranscriptNotFoundError(Exception):
    """A reunião existe, mas ainda não possui transcrição."""

class SummaryAlreadyProcessingError(Exception):
    """Já existe um processamento de resumo em andamento para a reunião informada."""

class SummaryService:
    def __init__(
            self,
            summarization: SummarizationService,
            summary_repository: SummaryRepository,
            meeting_repository: MeetingRepository,
            transcript_repository: TranscriptRepository,
            integration_service: IntegrationService | None = None,
    ) -> None:
        self.summarization = summarization
        self.summary_repository = summary_repository
        self.meeting_repository = meeting_repository
        self.transcript_repository = transcript_repository
        self.integration_service = integration_service or IntegrationService()

    def generate_and_persist(self, meeting_id: int) -> SummaryResponse:
        meeting = self.meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(meeting_id)

        if meeting.status == MeetingStatus.PROCESSING:
            raise SummaryAlreadyProcessingError(meeting_id)

        transcript = self.transcript_repository.get_by_meeting_id(meeting_id)
        if transcript is None or not transcript.raw_text.strip():
            raise TranscriptNotFoundError(meeting_id)

        previous_status = meeting.status
        self.meeting_repository.update_status(meeting, status=MeetingStatus.PROCESSING)

        try:
            result = self.summarization.summarize(transcript.raw_text)
            summary = self.summary_repository.save_result(
                meeting_id=meeting_id,
                result=result,
                generation_metadata={
                    "provider": settings.llm_provider or "gemini",
                    "model": settings.llm_model or "gemini-1.5-flash",
                },
            )

        except Exception:
            self.meeting_repository.update_status(meeting, status=previous_status)
            raise

        # O resumo e as tarefas já foram commitados pelo repositório; só então
        # marcamos a reunião como concluída e iniciamos entregas externas.
        self.meeting_repository.update_status(meeting, status=MeetingStatus.COMPLETED)
        response = SummaryResponse.model_validate(summary)
        try:
            self.integration_service.dispatch(response)
        except Exception:
            # Defesa adicional: erro de integração nunca altera o resultado principal.
            logger.exception("Falha inesperada ao despachar integrações da reunião %s", meeting_id)
        return response