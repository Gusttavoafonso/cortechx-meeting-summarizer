from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.retry import RetryPolicy
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_storage import AudioStorageService
from app.services.chunking import ChunkingService
from app.services.diarization import (
    DiarizationProvider,
    DiarizationSegment,
    DiarizationService,
    PyannoteDiarizationProvider,
)
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription import get_speech_to_text_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class _DefaultSpeakerDiarizationProvider(DiarizationProvider):
    """Provedor local de fallback caso HUGGINGFACE_TOKEN não esteja configurado."""

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        return [
            DiarizationSegment(
                speaker="SPEAKER_00",
                start_time=0.0,
                end_time=86400.0,
            )
        ]


def _get_worker_diarization_service(
    diarization_enabled: bool = True,
) -> DiarizationService:
    has_hf_token = bool(
        settings.huggingface_token
        and settings.huggingface_token.get_secret_value().strip()
    )
    provider: DiarizationProvider = (
        PyannoteDiarizationProvider()
        if (diarization_enabled and has_hf_token)
        else _DefaultSpeakerDiarizationProvider()
    )
    return DiarizationService(provider)


def _get_worker_stt_service(provider_pref: str | None = None):
    if provider_pref == "local":
        from app.services.transcription.faster_whisper_service import (
            FasterWhisperTranscriptionService,
        )

        return FasterWhisperTranscriptionService(
            model_size=settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    if provider_pref == "groq":
        has_groq = bool(
            settings.groq_api_key and settings.groq_api_key.get_secret_value().strip()
        )
        if has_groq:
            from app.services.transcription.groq_whisper_service import (
                GroqWhisperTranscriptionService,
            )

            return GroqWhisperTranscriptionService(
                api_key=settings.groq_api_key.get_secret_value().strip()
            )
    return get_speech_to_text_service()


def build_meeting_processor(
    session: Session,
    retry_policy: RetryPolicy | None = None,
    options: dict | None = None,
) -> MeetingProcessor:
    """Constrói o MeetingProcessor integrado à política centralizada de retry."""
    opts = options or {}

    summarization_service = None
    try:
        from app.services.llm.service import get_llm_service
        from app.services.summarization.service import create_summarization_service

        llm = get_llm_service()
        summarization_service = create_summarization_service(llm)
    except Exception:
        summarization_service = None

    return MeetingProcessor(
        meeting_repository=MeetingRepository(session),
        transcript_repository=TranscriptRepository(session),
        summary_repository=SummaryRepository(session),
        summarization_service=summarization_service,
        audio_storage_service=AudioStorageService(),
        speech_to_text_service=_get_worker_stt_service(opts.get("provider")),
        diarization_service=_get_worker_diarization_service(
            diarization_enabled=opts.get("diarization", True) is not False
        ),
        chunking_service=ChunkingService(),
        retry_policy=retry_policy or RetryPolicy.from_settings(),
    )


def run_meeting_processing_job(
    meeting_id: int,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    processor_factory: Callable[..., MeetingProcessor] = build_meeting_processor,
    options: dict | None = None,
) -> None:
    """Executa o pipeline completo em segundo plano com sessão de banco isolada."""
    session = session_factory()
    opts = options or {}
    try:
        try:
            try:
                processor = processor_factory(session, options=opts)
            except TypeError:
                processor = processor_factory(session)
        except Exception as proc_exc:
            meeting = session.get(Meeting, meeting_id)
            if meeting is not None:
                from app.core.failure_recorder import sanitize_error_message
                from app.services.meeting_service import MeetingService

                try:
                    MeetingService(MeetingRepository(session)).update_status(
                        meeting_id,
                        MeetingStatus.FAILED,
                        error_message=sanitize_error_message(str(proc_exc)),
                    )
                except Exception:
                    MeetingRepository(session).update_status(
                        meeting, MeetingStatus.FAILED
                    )
            raise
        language = opts.get("language")
        if language == "auto":
            language = None
        process_kwargs: dict = {"allow_already_processing": True}
        if language:
            process_kwargs["language"] = language
        if opts.get("auto_tasks") is False:
            process_kwargs["skip_tasks"] = True
        if opts.get("export_notion") is False:
            process_kwargs["skip_integrations"] = True
        processor.process_meeting(meeting_id, **process_kwargs)
    finally:
        session.close()


@celery_app.task(name="meetings.process_meeting")
def process_meeting_task(
    meeting_id: int, options: dict | None = None
) -> None:
    """Task Celery que delega a execução para run_meeting_processing_job."""
    run_meeting_processing_job(meeting_id, options=options)


def enqueue_meeting_processing(
    meeting_id: int,
    background_tasks: BackgroundTasks | None = None,
    options: dict | None = None,
) -> None:
    """Publica o job no Celery (com fallback local se indisponível)."""
    try:
        if options:
            process_meeting_task.delay(meeting_id, options=options)
        else:
            process_meeting_task.delay(meeting_id)
    except Exception as exc:
        if background_tasks is not None:
            logger.warning(
                "Broker Celery indisponível (%s). Executando reunião %s "
                "via BackgroundTasks.",
                exc,
                meeting_id,
            )
            if options:
                background_tasks.add_task(
                    run_meeting_processing_job, meeting_id, options=options
                )
            else:
                background_tasks.add_task(run_meeting_processing_job, meeting_id)
            return
        raise
