from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.api.v1.meetings import (
    get_audio_storage_service,
    get_diarization_service,
    get_meeting_job_dispatcher,
    get_transcription_service,
)
from app.main import app
from app.models.meeting import Meeting
from app.models.meeting_status import VALID_TRANSITIONS, MeetingStatus
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_storage import AudioStorageService
from app.services.chunking import ChunkingService
from app.services.diarization import DiarizationSegment
from app.services.meeting_service import (
    InvalidMeetingTransitionError,
    MeetingService,
)
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription import (
    MockSpeechToTextService,
    SegmentData,
    TranscriptionResult,
)
from app.workers.meeting_job import run_meeting_processing_job
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

VALID_SUMMARY_JSON = json.dumps(
    {
        "objective": "Alinhar a sprint",
        "summary": "A equipe alinhou as entregas da sprint.",
        "key_points": ["Finalizar o backend"],
        "decisions": ["Manter PostgreSQL"],
        "tasks": [],
    }
)

INVALID_TRANSITIONS = [
    (source, target)
    for source in MeetingStatus
    for target in MeetingStatus
    if source != target and target not in VALID_TRANSITIONS.get(source, set())
]


class FakeLLM:
    """LLM falso: devolve uma resposta fixa ou levanta o erro informado."""

    def __init__(
        self, response: str | None = None, error: Exception | None = None
    ) -> None:
        self.response = response
        self.error = error

    def generate(self, prompt: str) -> str:
        if self.error is not None:
            raise self.error
        return self.response or ""


def _noop_dispatcher(_meeting_id: int, _background_tasks=None) -> None:
    return None


@pytest.fixture(autouse=True)
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isola storage, STT, diarização, dispatcher e LLM para todos os testes."""
    audio_storage = AudioStorageService(base_storage_path=tmp_path)

    app.dependency_overrides[get_audio_storage_service] = lambda: audio_storage
    app.dependency_overrides[get_transcription_service] = lambda: (
        MockSpeechToTextService()
    )
    app.dependency_overrides[get_diarization_service] = lambda: MagicMock()
    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: _noop_dispatcher
    monkeypatch.setattr(
        "app.api.v1.meetings.get_llm_service",
        lambda: FakeLLM(response=VALID_SUMMARY_JSON),
    )

    yield audio_storage

    for dependency in (
        get_audio_storage_service,
        get_transcription_service,
        get_diarization_service,
        get_meeting_job_dispatcher,
    ):
        app.dependency_overrides.pop(dependency, None)


# Helpers


def _create_meeting(client: TestClient, title: str = "Reunião de status") -> int:
    response = client.post("/meetings", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def _create_meeting_with_audio(
    client: TestClient, title: str = "Reunião de status"
) -> int:
    meeting_id = _create_meeting(client, title)
    response = client.post(
        f"/meetings/{meeting_id}/audio",
        files={"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")},
    )
    assert response.status_code == 201
    return meeting_id


def _create_transcribed_meeting(client: TestClient) -> int:
    meeting_id = _create_meeting_with_audio(client)
    assert client.post(f"/meetings/{meeting_id}/transcribe").status_code == 200
    return meeting_id


def _get_status(client: TestClient, meeting_id: int) -> dict:
    response = client.get(f"/meetings/{meeting_id}/status")
    assert response.status_code == 200
    return response.json()


def _persisted(db_session: Session, meeting_id: int):
    """Lê as colunas de estado direto do banco, sem passar pela API."""
    return db_session.execute(
        select(
            Meeting.status,
            Meeting.last_error,
            Meeting.processing_started_at,
            Meeting.processing_completed_at,
        ).where(Meeting.id == meeting_id)
    ).one()


def _transcription(
    text: str = "Vamos finalizar o backend até sexta-feira.",
) -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        language="pt",
        duration=6.0,
        segments=[SegmentData(start=0.0, end=6.0, text=text, speaker=None)],
    )


def _run_worker(
    db_session: Session,
    audio_storage: AudioStorageService,
    meeting_id: int,
    stt_service: MagicMock,
    diarization_service: MagicMock,
) -> None:
    def build_processor(session: Session) -> MeetingProcessor:
        return MeetingProcessor(
            meeting_repository=MeetingRepository(session),
            transcript_repository=TranscriptRepository(session),
            audio_storage_service=audio_storage,
            speech_to_text_service=stt_service,
            diarization_service=diarization_service,
            chunking_service=ChunkingService(),
        )

    non_closing_session = MagicMock(wraps=db_session)
    non_closing_session.close = MagicMock()

    run_meeting_processing_job(
        meeting_id,
        session_factory=lambda: non_closing_session,
        processor_factory=build_processor,
    )


# Estado inicial, após upload e consulta pela API


def test_new_meeting_starts_as_received(client: TestClient) -> None:
    response = client.post("/meetings", json={"title": "Nova reunião"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "received"
    assert body["processing_started_at"] is None
    assert body["processing_completed_at"] is None
    assert body["last_error"] is None


def test_status_endpoint_returns_current_state(client: TestClient) -> None:
    meeting_id = _create_meeting(client)

    body = _get_status(client, meeting_id)

    assert {"meeting_id", "status", "updated_at"} <= body.keys()
    assert body["meeting_id"] == meeting_id
    assert body["status"] == "received"


def test_status_endpoint_returns_404_for_unknown_meeting(client: TestClient) -> None:
    assert client.get("/meetings/99999/status").status_code == 404


def test_status_endpoint_rejects_invalid_id(client: TestClient) -> None:
    assert client.get("/meetings/0/status").status_code == 400


def test_status_is_audio_uploaded_after_upload(client: TestClient) -> None:
    meeting_id = _create_meeting_with_audio(client)

    assert _get_status(client, meeting_id)["status"] == "audio_uploaded"
    assert client.get(f"/meetings/{meeting_id}").json()["status"] == "audio_uploaded"


# Início do processamento, durante e após o worker


def test_process_reserves_processing_state_and_start_time(
    client: TestClient, db_session: Session
) -> None:
    meeting_id = _create_meeting_with_audio(client)

    response = client.post(f"/meetings/{meeting_id}/process")

    assert response.status_code == 202
    assert _get_status(client, meeting_id)["status"] == "processing"
    row = _persisted(db_session, meeting_id)
    assert MeetingStatus(row.status) == MeetingStatus.PROCESSING
    assert row.processing_started_at is not None
    assert row.processing_completed_at is None


def test_status_is_processing_while_worker_runs_and_completed_after(
    client: TestClient, db_session: Session, storage: AudioStorageService
) -> None:
    meeting_id = _create_meeting_with_audio(client)
    assert client.post(f"/meetings/{meeting_id}/process").status_code == 202

    observed: list[str] = []

    def fake_transcribe(*_args, **_kwargs) -> TranscriptionResult:
        observed.append(MeetingStatus(_persisted(db_session, meeting_id).status).value)
        return _transcription()

    def fake_diarize(*_args, **_kwargs) -> list[DiarizationSegment]:
        observed.append(MeetingStatus(_persisted(db_session, meeting_id).status).value)
        return [DiarizationSegment(speaker="SPEAKER_00", start_time=0.0, end_time=6.0)]

    stt_service = MagicMock()
    stt_service.transcribe.side_effect = fake_transcribe
    diarization_service = MagicMock()
    diarization_service.diarize.side_effect = fake_diarize

    _run_worker(db_session, storage, meeting_id, stt_service, diarization_service)

    # Durante toda a execução do pipeline o estado permanece PROCESSING
    assert observed == ["processing", "processing"]

    row = _persisted(db_session, meeting_id)
    assert MeetingStatus(row.status) == MeetingStatus.COMPLETED
    assert row.last_error is None
    assert row.processing_started_at is not None
    assert row.processing_completed_at is not None
    assert _get_status(client, meeting_id)["status"] == "completed"


def test_worker_failure_persists_failed_status_and_last_error(
    client: TestClient, db_session: Session, storage: AudioStorageService
) -> None:
    meeting_id = _create_meeting_with_audio(client)
    assert client.post(f"/meetings/{meeting_id}/process").status_code == 202

    stt_service = MagicMock()
    stt_service.transcribe.side_effect = RuntimeError("STT indisponível")

    with pytest.raises(RuntimeError, match="STT indisponível"):
        _run_worker(db_session, storage, meeting_id, stt_service, MagicMock())

    row = _persisted(db_session, meeting_id)
    assert MeetingStatus(row.status) == MeetingStatus.FAILED
    assert row.last_error == "STT indisponível"
    assert row.processing_started_at is not None
    assert row.processing_completed_at is not None

    body = _get_status(client, meeting_id)
    assert body["status"] == "failed"
    assert body["last_error"] == "STT indisponível"


def test_new_attempt_after_failure_clears_previous_error(
    client: TestClient, db_session: Session, storage: AudioStorageService
) -> None:
    meeting_id = _create_meeting_with_audio(client)
    assert client.post(f"/meetings/{meeting_id}/process").status_code == 202

    stt_service = MagicMock()
    stt_service.transcribe.side_effect = RuntimeError("falha temporária")
    with pytest.raises(RuntimeError):
        _run_worker(db_session, storage, meeting_id, stt_service, MagicMock())
    assert _get_status(client, meeting_id)["status"] == "failed"

    # Nova tentativa a partir de FAILED
    assert client.post(f"/meetings/{meeting_id}/process").status_code == 202

    row = _persisted(db_session, meeting_id)
    assert MeetingStatus(row.status) == MeetingStatus.PROCESSING
    assert row.last_error is None
    assert row.processing_completed_at is None
    assert row.processing_started_at is not None


# Transições (service) e metadados de falha


@pytest.mark.parametrize(
    ("source", "target"),
    INVALID_TRANSITIONS,
    ids=lambda status: status.value,
)
def test_service_rejects_invalid_transition(
    db_session: Session, source: MeetingStatus, target: MeetingStatus
) -> None:
    repository = MeetingRepository(db_session)
    meeting = repository.create(Meeting(title="Transição inválida", status=source))

    with pytest.raises(InvalidMeetingTransitionError):
        MeetingService(repository).update_status(meeting.id, target)

    assert MeetingStatus(repository.get_by_id(meeting.id).status) == source


def test_failed_transition_records_error_and_completion_time(
    db_session: Session,
) -> None:
    repository = MeetingRepository(db_session)
    meeting = repository.create(Meeting(title="Falha", status=MeetingStatus.PROCESSING))

    updated = MeetingService(repository).update_status(
        meeting.id, MeetingStatus.FAILED, error_message="boom"
    )

    assert MeetingStatus(updated.status) == MeetingStatus.FAILED
    assert updated.last_error == "boom"
    assert updated.processing_completed_at is not None


def test_error_message_is_truncated_to_2000_characters(db_session: Session) -> None:
    repository = MeetingRepository(db_session)
    meeting = repository.create(Meeting(title="Falha", status=MeetingStatus.PROCESSING))

    updated = MeetingService(repository).update_status(
        meeting.id, MeetingStatus.FAILED, error_message="x" * 5000
    )

    assert len(updated.last_error) == 2000


@pytest.mark.parametrize(
    "target",
    [
        MeetingStatus.AUDIO_UPLOADED,
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.PROCESSING,
    ],
    ids=lambda status: status.value,
)
def test_failed_meeting_can_be_retried_and_error_is_cleared(
    db_session: Session, target: MeetingStatus
) -> None:
    repository = MeetingRepository(db_session)
    service = MeetingService(repository)
    meeting = repository.create(
        Meeting(title="Retomada", status=MeetingStatus.PROCESSING)
    )
    service.update_status(
        meeting.id, MeetingStatus.FAILED, error_message="erro anterior"
    )

    retried = service.update_status(meeting.id, target)

    assert MeetingStatus(retried.status) == target
    assert retried.last_error is None


def test_invalid_transition_through_api_returns_409(
    client: TestClient, db_session: Session
) -> None:
    meeting_id = _create_meeting_with_audio(client)
    repository = MeetingRepository(db_session)
    # Força COMPLETED direto no repository (sem validação de transição)
    repository.update_status(repository.get_by_id(meeting_id), MeetingStatus.COMPLETED)

    response = client.post(f"/meetings/{meeting_id}/transcribe")

    assert response.status_code == 409
    assert "inválida" in response.json()["detail"]
    assert _get_status(client, meeting_id)["status"] == "completed"


# Processamento duplicado / simultâneo


@pytest.mark.parametrize("action", ["transcribe", "diarize", "summary", "process"])
def test_actions_are_rejected_while_meeting_is_processing(
    client: TestClient, action: str
) -> None:
    meeting_id = _create_meeting_with_audio(client)
    assert client.post(f"/meetings/{meeting_id}/process").status_code == 202

    response = client.post(f"/meetings/{meeting_id}/{action}")

    assert response.status_code == 409
    assert _get_status(client, meeting_id)["status"] == "processing"


# Fluxo síncrono de resumo: COMPLETED / FAILED / retentativa


def test_summary_success_marks_meeting_completed(client: TestClient) -> None:
    meeting_id = _create_transcribed_meeting(client)
    assert _get_status(client, meeting_id)["status"] == "transcribed"

    response = client.post(f"/meetings/{meeting_id}/summary")

    assert response.status_code == 201
    meeting = client.get(f"/meetings/{meeting_id}").json()
    assert meeting["status"] == "completed"
    assert meeting["processing_started_at"] is not None
    assert meeting["processing_completed_at"] is not None
    assert meeting["last_error"] is None


def test_summary_failure_marks_meeting_failed_and_can_be_retried(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting_id = _create_transcribed_meeting(client)

    monkeypatch.setattr(
        "app.api.v1.meetings.get_llm_service",
        lambda: FakeLLM(error=RuntimeError("quota excedida")),
    )
    response = client.post(f"/meetings/{meeting_id}/summary")

    assert response.status_code == 502
    body = _get_status(client, meeting_id)
    assert body["status"] == "failed"
    assert body["last_error"]
    assert client.get(f"/meetings/{meeting_id}/summary").status_code == 404

    # Retentativa com o LLM funcionando
    monkeypatch.setattr(
        "app.api.v1.meetings.get_llm_service",
        lambda: FakeLLM(response=VALID_SUMMARY_JSON),
    )
    retry = client.post(f"/meetings/{meeting_id}/summary")

    assert retry.status_code == 201
    body = _get_status(client, meeting_id)
    assert body["status"] == "completed"
    assert body["last_error"] is None
