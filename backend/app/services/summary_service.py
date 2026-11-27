from app.core.config import settings
from app.core.exceptions import (
    MeetingNotFoundError,
    SummaryAlreadyProcessingError,
    TranscriptNotFoundError,
)
from app.models.meeting_status import IN_PROGRESS_STATUSES, MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.summary import SummaryResponse
from app.services.meeting_service import MeetingService
from app.services.summarization.service import SummarizationService


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
        self.meeting_service = MeetingService(meeting_repository)

    def generate_and_persist(self, meeting_id: int) -> SummaryResponse:
        meeting = self.meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(meeting_id)

        if MeetingStatus(meeting.status) in IN_PROGRESS_STATUSES:
            raise SummaryAlreadyProcessingError(meeting_id)

        transcript = self.transcript_repository.get_by_meeting_id(meeting_id)
        if transcript is None or not transcript.raw_text.strip():
            raise TranscriptNotFoundError(meeting_id)

        self.meeting_service.update_status(meeting_id, MeetingStatus.PROCESSING)

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

        except Exception as exc:
            self.meeting_repository.db.rollback()
            self.meeting_service.update_status(
                meeting_id,
                MeetingStatus.FAILED,
                error_message=str(exc) or exc.__class__.__name__,
            )
            raise

        self.meeting_service.update_status(meeting_id, MeetingStatus.COMPLETED)
        return SummaryResponse.model_validate(summary)
