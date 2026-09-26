from __future__ import annotations

import logging

from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_storage import AudioStorageService
from app.services.chunking import ChunkingService
from app.services.diarization import DiarizationService
from app.services.transcription import BaseSpeechToTextService

logger = logging.getLogger(__name__)


class MeetingProcessor:
    def __init__(
        self,
        meeting_repository: MeetingRepository,
        transcript_repository: TranscriptRepository,
        audio_storage_service: AudioStorageService,
        speech_to_text_service: BaseSpeechToTextService,
        diarization_service: DiarizationService,
        chunking_service: ChunkingService,
    ) -> None:
        self._meeting_repository = meeting_repository
        self._transcript_repository = transcript_repository
        self._audio_storage_service = audio_storage_service
        self._speech_to_text_service = speech_to_text_service
        self._diarization_service = diarization_service
        self._chunking_service = chunking_service

    # serviço de orquestração do processamento de reuniões
    def process_meeting(self, meeting_id: int) -> None:
        meeting = self._get_meeting(meeting_id)

        if meeting.audio is None:
            raise ValueError(f"Missing audio from Meeting {meeting_id}")

        if meeting.status == MeetingStatus.PROCESSING:
            raise ValueError(
                f"Meeting with ID {meeting_id} is already being processed."
            )

        self._meeting_repository.update_status(
            meeting,
            MeetingStatus.PROCESSING,
        )

        try:
            audio_path = self._audio_storage_service.get_file_path(
                meeting.audio.file_path,
            )

            stt = self._speech_to_text_service.transcribe(audio_path)

            transcript = self._transcript_repository.save_transcript(
                meeting_id=meeting_id, content=stt.text, segments=stt.segments
            )

            diarization_segments = self._diarization_service.diarize(audio_path)

            self._transcript_repository.apply_diarization(
                transcript,
                diarization_segments,
            )

            self._chunking_service.split(transcript)

            self._meeting_repository.update_status(
                meeting,
                MeetingStatus.COMPLETED,
            )

        except Exception:
            logger.exception("Falha ao processar reunião %s", meeting_id)
            self._meeting_repository.update_status(
                meeting,
                MeetingStatus.FAILED,
            )
            raise

    # função para buscar a reunião no banco de dados
    def _get_meeting(self, meeting_id: int) -> Meeting:
        meeting = self._meeting_repository.get_by_id(meeting_id)

        if meeting is None:
            raise ValueError(f"Meeting with ID {meeting_id} not found.")
        return meeting
