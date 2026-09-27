from __future__ import annotations

import io
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.api.v1.meetings import (
    get_audio_storage_service,
    get_meeting_job_dispatcher,
)
from app.main import app
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_storage import AudioStorageService
from app.services.chunking import ChunkingService
from app.services.diarization import DiarizationSegment
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription.base import SegmentData, TranscriptionResult
from app.workers.meeting_job import run_meeting_processing_job
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def temp_storage_service(tmp_path: Path) -> AudioStorageService:
    storage = AudioStorageService(base_storage_path=tmp_path)
    app.dependency_overrides[get_audio_storage_service] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_audio_storage_service, None)


def _upload_sample_audio(client: TestClient, meeting_id: int) -> None:
    wav_bytes = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    response = client.post(
        f"/meetings/{meeting_id}/audio",
        files={"file": ("reuniao.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert response.status_code == 201


def test_post_process_returns_404_for_nonexistent_meeting(
    client: TestClient,
) -> None:
    dispatcher = MagicMock()
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: dispatcher

    response = client.post("/meetings/9999/process")

    assert response.status_code == 404
    dispatcher.assert_not_called()


def test_post_process_returns_404_when_meeting_has_no_audio(
    client: TestClient,
) -> None:
    dispatcher = MagicMock()
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: dispatcher

    create_resp = client.post("/meetings", json={"title": "Reunião sem áudio"})
    meeting_id = create_resp.json()["id"]

    response = client.post(f"/meetings/{meeting_id}/process")

    assert response.status_code == 404
    dispatcher.assert_not_called()


def test_post_process_dispatches_job_and_returns_immediately_without_waiting(
    client: TestClient,
    temp_storage_service: AudioStorageService,
) -> None:
    dispatched_ids: list[int] = []

    def fake_dispatcher(meeting_id: int, _bg=None) -> None:
        dispatched_ids.append(meeting_id)

    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: fake_dispatcher

    create_resp = client.post("/meetings", json={"title": "Sprint Review"})
    meeting_id = create_resp.json()["id"]
    _upload_sample_audio(client, meeting_id)

    start = time.perf_counter()
    response = client.post(f"/meetings/{meeting_id}/process")
    elapsed = time.perf_counter() - start

    assert response.status_code == 202
    assert response.json() == {
        "meeting_id": meeting_id,
        "status": "PROCESSING",
    }
    assert dispatched_ids == [meeting_id]
    assert elapsed < 0.5


def test_post_process_rejects_duplicate_concurrent_processing(
    client: TestClient,
    temp_storage_service: AudioStorageService,
) -> None:
    dispatcher = MagicMock()
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: dispatcher

    create_resp = client.post("/meetings", json={"title": "Daily"})
    meeting_id = create_resp.json()["id"]
    _upload_sample_audio(client, meeting_id)

    first_response = client.post(f"/meetings/{meeting_id}/process")
    assert first_response.status_code == 202

    second_response = client.post(f"/meetings/{meeting_id}/process")
    assert second_response.status_code == 409
    assert dispatcher.call_count == 1


def test_end_to_end_async_processing_pipeline_execution(
    client: TestClient,
    db_session: Session,
    temp_storage_service: AudioStorageService,
) -> None:
    """Valida o fluxo completo de processamento assíncrono em background:
    POST /meetings -> POST /meetings/{id}/audio -> POST /meetings/{id}/process
    -> Worker executa pipeline completo -> GET /meetings/{id} (COMPLETED) e
    GET /meetings/{id}/transcript.
    """
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: (
        lambda _mid, _bg=None: None
    )

    create_resp = client.post("/meetings", json={"title": "Planejamento Q4"})
    assert create_resp.status_code == 201
    meeting_id = create_resp.json()["id"]

    _upload_sample_audio(client, meeting_id)

    process_resp = client.post(f"/meetings/{meeting_id}/process")
    assert process_resp.status_code == 202
    assert process_resp.json()["status"] == "PROCESSING"

    # Antes do worker concluir, GET /transcript deve retornar 404
    early_transcript = client.get(f"/meetings/{meeting_id}/transcript")
    assert early_transcript.status_code == 404

    stt_service = MagicMock()
    stt_service.transcribe.return_value = TranscriptionResult(
        text="Vamos implementar o worker Celery até sexta-feira.",
        language="pt",
        duration=12.0,
        segments=[
            SegmentData(
                start=0.0,
                end=6.0,
                text="Vamos implementar o worker Celery até sexta-feira.",
                speaker=None,
            )
        ],
    )

    diarization_service = MagicMock()
    diarization_service.diarize.return_value = [
        DiarizationSegment(
            speaker="SPEAKER_00",
            start_time=0.0,
            end_time=6.0,
        )
    ]

    summarization_service = MagicMock()
    summarization_service.summarize.return_value = MagicMock(
        objective="Definir entrega do processamento assíncrono",
        summary="A equipe acordou a implementação do worker Celery com Redis.",
        main_points=["Implementar rota POST /process", "Integrar Celery"],
        decisions=["Usar Redis como broker de mensagens"],
    )
    task_extraction_service = MagicMock()
    task_extraction_service.extract_tasks.return_value = [
        {"description": "Implementar worker Celery", "assignee": "SPEAKER_00"}
    ]
    summary_repository = MagicMock()

    def build_test_processor(session: Session) -> MeetingProcessor:
        return MeetingProcessor(
            meeting_repository=MeetingRepository(session),
            transcript_repository=TranscriptRepository(session),
            summary_repository=summary_repository,
            audio_storage_service=temp_storage_service,
            speech_to_text_service=stt_service,
            diarization_service=diarization_service,
            chunking_service=ChunkingService(),
            summarization_service=summarization_service,
            task_extraction_service=task_extraction_service,
        )

    non_closing_session = MagicMock(wraps=db_session)
    non_closing_session.close = MagicMock()

    run_meeting_processing_job(
        meeting_id,
        session_factory=lambda: non_closing_session,
        processor_factory=build_test_processor,
    )

    non_closing_session.close.assert_called_once()
    summary_repository.save_summary.assert_called_once()

    meeting_resp = client.get(f"/meetings/{meeting_id}")
    assert meeting_resp.status_code == 200
    assert meeting_resp.json()["status"] == "completed"

    transcript_resp = client.get(f"/meetings/{meeting_id}/transcript")
    assert transcript_resp.status_code == 200
    t_body = transcript_resp.json()
    assert len(t_body["segments"]) == 1
    assert t_body["segments"][0]["speaker"] == "SPEAKER_00"


@pytest.fixture(autouse=True)
def reset_dispatcher_override():
    yield
    app.dependency_overrides.pop(get_meeting_job_dispatcher, None)


def test_worker_closes_session_even_when_processor_raises() -> None:
    fake_session = MagicMock()
    failing_processor = MagicMock()
    failing_processor.process_meeting.side_effect = RuntimeError("Pipeline crashed")

    with pytest.raises(RuntimeError, match="Pipeline crashed"):
        run_meeting_processing_job(
            42,
            session_factory=lambda: fake_session,
            processor_factory=lambda _s: failing_processor,
        )

    fake_session.close.assert_called_once()


def test_atomic_rollback_on_llm_failure_prevents_partial_transcript_and_marks_failed(
    client: TestClient,
    db_session: Session,
    temp_storage_service: AudioStorageService,
) -> None:
    """Garante que uma falha na etapa de LLM em uma sessão real do SQLAlchemy
    desfaz a Transcript/Diarização parcial (rollback) e grava status = FAILED
    sem lançar PendingRollbackError.
    """
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: (
        lambda _mid, _bg=None: None
    )

    create_resp = client.post("/meetings", json={"title": "Reunião Atomicidade"})
    meeting_id = create_resp.json()["id"]
    _upload_sample_audio(client, meeting_id)

    client.post(f"/meetings/{meeting_id}/process")

    stt_service = MagicMock()
    stt_service.transcribe.return_value = TranscriptionResult(
        text="Fala que não deve ficar órfã se o LLM falhar.",
        language="pt",
        duration=5.0,
        segments=[
            SegmentData(
                start=0.0,
                end=5.0,
                text="Fala que não deve ficar órfã se o LLM falhar.",
                speaker=None,
            )
        ],
    )
    diarization_service = MagicMock()
    diarization_service.diarize.return_value = [
        DiarizationSegment(speaker="SPEAKER_01", start_time=0.0, end_time=5.0)
    ]
    failing_summarizer = MagicMock()
    failing_summarizer.summarize.side_effect = RuntimeError("LLM quota exceeded")

    processor = MeetingProcessor(
        meeting_repository=MeetingRepository(db_session),
        transcript_repository=TranscriptRepository(db_session),
        audio_storage_service=temp_storage_service,
        speech_to_text_service=stt_service,
        diarization_service=diarization_service,
        chunking_service=ChunkingService(),
        summarization_service=failing_summarizer,
    )

    with pytest.raises(RuntimeError, match="LLM quota exceeded"):
        processor.process_meeting(meeting_id, allow_already_processing=True)

    # A transcrição intermediária deve ter sofrido rollback completo
    assert TranscriptRepository(db_session).get_by_meeting_id(meeting_id) is None

    # E o status da reunião no banco deve ter sido atualizado para FAILED
    updated_meeting = MeetingRepository(db_session).get_by_id(meeting_id)
    assert updated_meeting is not None
    assert updated_meeting.status.value == "failed"


def test_upload_audio_is_blocked_while_meeting_is_processing(
    client: TestClient,
    temp_storage_service: AudioStorageService,
) -> None:
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: (
        lambda _mid, _bg=None: None
    )

    create_resp = client.post("/meetings", json={"title": "Reunião Bloqueada"})
    meeting_id = create_resp.json()["id"]
    _upload_sample_audio(client, meeting_id)

    process_resp = client.post(f"/meetings/{meeting_id}/process")
    assert process_resp.status_code == 202

    wav_bytes = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    replace_resp = client.post(
        f"/meetings/{meeting_id}/audio",
        files={"file": ("novo.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert replace_resp.status_code == 409


def test_enqueue_meeting_processing_calls_celery_and_falls_back_to_background_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers import meeting_job
    from fastapi import BackgroundTasks

    delay_mock = MagicMock()
    monkeypatch.setattr(meeting_job.process_meeting_task, "delay", delay_mock)

    meeting_job.enqueue_meeting_processing(10)
    delay_mock.assert_called_once_with(10)

    delay_mock.side_effect = ConnectionError("Redis offline")
    bg_tasks = BackgroundTasks()
    meeting_job.enqueue_meeting_processing(10, background_tasks=bg_tasks)
    assert len(bg_tasks.tasks) == 1

