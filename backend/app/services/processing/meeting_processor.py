from __future__ import annotations

import logging
from typing import Any

from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_storage import AudioStorageService
from app.services.chunking import ChunkingService
from app.services.diarization import DiarizationService
from app.services.transcription import BaseSpeechToTextService
from sqlalchemy.orm import Session

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
        summarization_service: Any | None = None,
        task_extraction_service: Any | None = None,
        summary_repository: Any | None = None,
    ) -> None:
        self._meeting_repository = meeting_repository
        self._transcript_repository = transcript_repository
        self._audio_storage_service = audio_storage_service
        self._speech_to_text_service = speech_to_text_service
        self._diarization_service = diarization_service
        self._chunking_service = chunking_service
        self._summarization_service = summarization_service
        self._task_extraction_service = task_extraction_service
        self._summary_repository = summary_repository

    # serviço de orquestração do processamento de reuniões
    def process_meeting(
        self,
        meeting_id: int,
        *,
        allow_already_processing: bool = False,
    ) -> None:
        meeting = self._get_meeting(meeting_id)

        if meeting.audio is None:
            if allow_already_processing and meeting.status == MeetingStatus.PROCESSING:
                self._meeting_repository.update_status(meeting, MeetingStatus.FAILED)
            raise ValueError(f"Missing audio from Meeting {meeting_id}")

        if (
            meeting.status == MeetingStatus.PROCESSING
            and not allow_already_processing
        ):
            raise ValueError(
                f"Meeting with ID {meeting_id} is already being processed."
            )

        if meeting.status != MeetingStatus.PROCESSING:
            self._meeting_repository.update_status(
                meeting,
                MeetingStatus.PROCESSING,
            )

        use_atomic_unit_of_work = isinstance(
            getattr(self._meeting_repository, "db", None), Session
        )

        try:
            if (
                self._audio_storage_service.file_exists(meeting.audio.file_path)
                is False
            ):
                raise FileNotFoundError(
                    f"Audio file not found in storage for Meeting {meeting_id}"
                )

            audio_path = self._audio_storage_service.get_file_path(
                meeting.audio.file_path,
            )

            stt = self._speech_to_text_service.transcribe(audio_path)
            if not stt.text or not stt.text.strip():
                raise ValueError(
                    f"Empty transcription returned for Meeting {meeting_id}"
                )

            if use_atomic_unit_of_work:
                transcript = self._transcript_repository.save_transcript(
                    meeting_id=meeting_id,
                    content=stt.text,
                    segments=stt.segments,
                    commit=False,
                )
            else:
                transcript = self._transcript_repository.save_transcript(
                    meeting_id=meeting_id,
                    content=stt.text,
                    segments=stt.segments,
                )

            diarization_segments = self._diarization_service.diarize(audio_path)

            if use_atomic_unit_of_work:
                self._transcript_repository.apply_diarization(
                    transcript,
                    diarization_segments,
                    commit=False,
                )
            else:
                self._transcript_repository.apply_diarization(
                    transcript,
                    diarization_segments,
                )

            chunks = self._chunking_service.split(transcript)

            summary_result = (
                self._summarization_service.summarize(chunks)
                if self._summarization_service is not None
                else None
            )
            extracted_tasks = (
                self._task_extraction_service.extract_tasks(chunks)
                if self._task_extraction_service is not None
                else []
            )

            if self._summary_repository is not None and summary_result is not None:
                if use_atomic_unit_of_work:
                    self._summary_repository.save_summary(
                        meeting_id=meeting_id,
                        objective=summary_result.objective,
                        summary=summary_result.summary,
                        main_points=summary_result.main_points,
                        decisions=summary_result.decisions,
                        tasks=extracted_tasks,
                        commit=False,
                    )
                else:
                    self._summary_repository.save_summary(
                        meeting_id=meeting_id,
                        objective=summary_result.objective,
                        summary=summary_result.summary,
                        main_points=summary_result.main_points,
                        decisions=summary_result.decisions,
                        tasks=extracted_tasks,
                    )

            self._meeting_repository.update_status(
                meeting,
                MeetingStatus.COMPLETED,
            )

        except Exception:
            logger.exception("Falha ao processar reunião %s", meeting_id)
            self._rollback_if_needed()
            self._meeting_repository.update_status(
                meeting,
                MeetingStatus.FAILED,
            )
            raise

    def _rollback_if_needed(self) -> None:
        db = getattr(self._meeting_repository, "db", None)
        if db is not None and hasattr(db, "rollback"):
            db.rollback()

    # função para buscar a reunião no banco de dados
    def _get_meeting(self, meeting_id: int) -> Meeting:
        meeting = self._meeting_repository.get_by_id(meeting_id)

        if meeting is None:
            raise ValueError(f"Meeting with ID {meeting_id} not found.")
        return meeting
