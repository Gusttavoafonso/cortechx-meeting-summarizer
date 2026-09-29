from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.summary import SummaryResponse
from app.services.summarization.service import SummarizationService

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
    ) -> None:
        self.summarization = summarization
        self.summary_repository = summary_repository
        self.meeting_repository = meeting_repository
        self.transcript_repository = transcript_repository

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
                    "provider": "gemini",
                    "model": "gemini-3.6-flash",
                },
            )

        except Exception:
            self.meeting_repository.update_status(meeting, status=previous_status)
            raise

        self.meeting_repository.update_status(meeting, status=MeetingStatus.COMPLETED)
        return SummaryResponse.model_validate(summary)