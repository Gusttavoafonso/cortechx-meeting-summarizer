from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.retry import RetryPolicy
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_storage import AudioStorageService
from app.services.chunking import ChunkingService
from app.services.diarization import DiarizationService
from app.services.transcription import BaseSpeechToTextService
from app.workers.job_runner import JobRunner

logger = logging.getLogger(__name__)


class MeetingProcessor:
    """Orquestrador do processamento de reuniões integrado à política de retry.

    Executa o pipeline completo:
    Audio -> STT -> Diarização -> Chunking -> Sumarização / Tasks -> Persistência.

    Cada operação do pipeline é orquestrada através do JobRunner / RetryPolicy,
    garantindo que:
    1. Erros recuperáveis sofram retry automático com backoff exponencial.
    2. Erros definitivos abortem imediatamente sem retries.
    3. Em caso de falha definitiva ou esgotamento, o status seja atualizado para FAILED.
    """

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
        retry_policy: RetryPolicy | None = None,
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
        self._retry_policy = retry_policy or RetryPolicy.from_settings()
        self._job_runner = JobRunner(
            retry_policy=self._retry_policy,
            meeting_repository=self._meeting_repository,
        )

    def process_meeting(
        self,
        meeting_id: int,
        *,
        allow_already_processing: bool = False,
    ) -> None:
        """Executa o processamento da reunião sob controle de retry e ciclo de vida."""
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
            if not self._audio_storage_service.file_exists(meeting.audio.file_path):
                raise FileNotFoundError(
                    f"Audio file not found in storage for Meeting {meeting_id}"
                )

            audio_path = self._audio_storage_service.get_file_path(
                meeting.audio.file_path,
            )

            # 1. Operação Speech-to-Text via JobRunner (sucesso continua, recuperável retenta, definitivo FAILED)
            stt = self._job_runner.execute_operation(
                self._speech_to_text_service.transcribe,
                audio_path,
                meeting=meeting,
            )
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

            # 2. Operação Diarização via JobRunner
            diarization_segments = self._job_runner.execute_operation(
                self._diarization_service.diarize,
                audio_path,
                meeting=meeting,
            )

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

            # 3. Chunking
            chunks = self._chunking_service.split(transcript)

            # 4. Operações de LLM (Sumarização e Extração de Tarefas)
            summary_result = None
            if self._summarization_service is not None:
                summary_result = self._job_runner.execute_operation(
                    self._summarization_service.summarize,
                    chunks,
                    meeting=meeting,
                )

            extracted_tasks = []
            if self._task_extraction_service is not None:
                extracted_tasks = self._job_runner.execute_operation(
                    self._task_extraction_service.extract_tasks,
                    chunks,
                    meeting=meeting,
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
            logger.exception("Falha no pipeline da reunião %s", meeting_id)
            self._rollback_if_needed()
            try:
                self._meeting_repository.update_status(
                    meeting,
                    MeetingStatus.FAILED,
                )
            except Exception:
                pass
            raise

    def _rollback_if_needed(self) -> None:
        db = getattr(self._meeting_repository, "db", None)
        if db is not None and hasattr(db, "rollback"):
            db.rollback()

    def _get_meeting(self, meeting_id: int) -> Meeting:
        meeting = self._meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise ValueError(f"Meeting with ID {meeting_id} not found.")
        return meeting
