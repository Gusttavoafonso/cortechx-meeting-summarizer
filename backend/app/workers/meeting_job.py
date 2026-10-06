from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.retry import RetryPolicy
from app.repositories.meeting_repository import MeetingRepository
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


def _get_worker_diarization_service() -> DiarizationService:
    has_hf_token = bool(
        settings.huggingface_token
        and settings.huggingface_token.get_secret_value().strip()
    )
    provider: DiarizationProvider = (
        PyannoteDiarizationProvider()
        if has_hf_token
        else _DefaultSpeakerDiarizationProvider()
    )
    return DiarizationService(provider)


def build_meeting_processor(
    session: Session,
    retry_policy: RetryPolicy | None = None,
) -> MeetingProcessor:
    """Constrói o MeetingProcessor integrado à política centralizada de retry."""
    return MeetingProcessor(
        meeting_repository=MeetingRepository(session),
        transcript_repository=TranscriptRepository(session),
        audio_storage_service=AudioStorageService(),
        speech_to_text_service=get_speech_to_text_service(),
        diarization_service=_get_worker_diarization_service(),
        chunking_service=ChunkingService(),
        retry_policy=retry_policy or RetryPolicy.from_settings(),
    )


def run_meeting_processing_job(
    meeting_id: int,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    processor_factory: Callable[[Session], MeetingProcessor] = build_meeting_processor,
) -> None:
    """Executa o pipeline completo em segundo plano sob política de retry."""
    session = session_factory()
    try:
        processor = processor_factory(session)
        processor.process_meeting(
            meeting_id,
            allow_already_processing=True,
        )
    finally:
        session.close()


def enqueue_meeting_processing(
    meeting_id: int,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Enfileira o job assíncrono para a reunião informada."""
    # Tenta usar Celery caso esteja disponível
    try:
        from app.workers.celery_app import celery_app  # type: ignore

        if celery_app is not None:
            celery_app.send_task("meetings.process_meeting", args=[meeting_id])
            return
    except Exception as exc:
        logger.debug("Celery indisponível (%s). Usando fallback assíncrono.", exc)

    if background_tasks is not None:
        logger.info(
            "Executando processamento da reunião %s via BackgroundTasks.",
            meeting_id,
        )
        background_tasks.add_task(run_meeting_processing_job, meeting_id)
        return

    logger.info("Executando processamento direto da reunião %s.", meeting_id)
    run_meeting_processing_job(meeting_id)
