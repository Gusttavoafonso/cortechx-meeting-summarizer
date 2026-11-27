from __future__ import annotations

import logging
from collections.abc import Callable

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
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription import get_speech_to_text_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_worker_stt_service(
    provider_pref: str | None = None,
    *,
    user_groq_api_key: str | None = None,
):
    if provider_pref == "local":
        from app.services.transcription.faster_whisper_service import (
            FasterWhisperService,
        )

        return FasterWhisperService(
            model_size=settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    if user_groq_api_key and user_groq_api_key.strip() and provider_pref in (
        None,
        "auto",
        "groq",
    ):
        from app.services.transcription.groq_whisper_service import (
            GroqWhisperService,
        )

        return GroqWhisperService(api_key=user_groq_api_key.strip())
    if provider_pref == "groq":
        has_groq = bool(
            settings.groq_api_key and settings.groq_api_key.get_secret_value().strip()
        )
        if has_groq:
            from app.services.transcription.groq_whisper_service import (
                GroqWhisperService,
            )

            return GroqWhisperService(
                api_key=settings.groq_api_key.get_secret_value().strip()
            )
    return get_speech_to_text_service()


def _resolve_user_groq_key(session: Session, meeting_id: int | None) -> str | None:
    if meeting_id is None:
        return None
    from sqlalchemy import select

    from app.core.secret_crypto import SecretDecryptionError, decrypt_secret
    from app.models.user_integration import UserIntegration

    meeting = session.get(Meeting, meeting_id)
    if meeting is None or meeting.user_id is None:
        return None
    integration = session.scalar(
        select(UserIntegration).where(
            UserIntegration.user_id == meeting.user_id,
            UserIntegration.provider == "groq",
            UserIntegration.enabled.is_(True),
        )
    )
    if integration is None or not isinstance(integration.config, dict):
        return None
    raw_key = integration.config.get("api_key")
    if isinstance(raw_key, str) and raw_key.strip():
        try:
            decrypted = decrypt_secret(
                raw_key,
                user_id=meeting.user_id,
                provider="groq",
                field="api_key",
            ).strip()
            return decrypted or None
        except SecretDecryptionError:
            logger.warning(
                "Falha ao descriptografar chave Groq do usuário %s.",
                meeting.user_id,
            )
            return None
    return None


def build_meeting_processor(
    session: Session,
    retry_policy: RetryPolicy | None = None,
    options: dict | None = None,
    *,
    meeting_id: int | None = None,
) -> MeetingProcessor:
    """Constrói o MeetingProcessor integrado à política centralizada de retry."""
    from app.services.llm.service import get_llm_service, resolve_user_llm_config
    from app.services.summarization.service import create_summarization_service
    from app.services.task_extraction.service import TaskExtractionService

    opts = options or {}

    chunking = ChunkingService()
    meeting = session.get(Meeting, meeting_id) if meeting_id is not None else None
    user_llm_cfg = resolve_user_llm_config(
        session, meeting.user_id if meeting is not None else None
    )
    if user_llm_cfg is not None:
        llm = get_llm_service(
            provider=user_llm_cfg["provider"],
            model=user_llm_cfg["model"],
            api_key=user_llm_cfg["api_key"],
        )
    else:
        llm = get_llm_service()
    summarization_service = create_summarization_service(llm)
    task_extraction_service = TaskExtractionService(
        llm_service=llm,
        chunking_service=chunking,
    )
    user_groq_key = _resolve_user_groq_key(session, meeting_id)

    return MeetingProcessor(
        meeting_repository=MeetingRepository(session),
        transcript_repository=TranscriptRepository(session),
        summary_repository=SummaryRepository(session),
        summarization_service=summarization_service,
        task_extraction_service=task_extraction_service,
        audio_storage_service=AudioStorageService(),
        speech_to_text_service=_get_worker_stt_service(
            opts.get("provider"),
            user_groq_api_key=user_groq_key,
        ),
        chunking_service=chunking,
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
                processor = processor_factory(
                    session, options=opts, meeting_id=meeting_id
                )
            except TypeError:
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
        if opts.get("skip_integrations") is True:
            process_kwargs["skip_integrations"] = True
        else:
            integrations = opts.get("integrations")
            if integrations is not None:
                selected = [
                    str(p).strip().lower() for p in integrations if str(p).strip()
                ]
                if opts.get("export_notion") is False:
                    selected = [p for p in selected if p != "notion"]
                process_kwargs["integration_providers"] = selected
            elif opts.get("export_notion") is False:
                process_kwargs["excluded_providers"] = ["notion"]
        processor.process_meeting(meeting_id, **process_kwargs)
    finally:
        session.close()


@celery_app.task(name="meetings.process_meeting")
def process_meeting_task(
    meeting_id: int, options: dict | None = None
) -> None:
    """Task Celery que delega a execução para run_meeting_processing_job."""
    if options is not None:
        run_meeting_processing_job(meeting_id, options=options)
    else:
        run_meeting_processing_job(meeting_id)


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
