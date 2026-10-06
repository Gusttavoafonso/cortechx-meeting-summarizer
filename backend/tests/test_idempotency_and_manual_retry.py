import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.retry import RetryPolicy
from app.main import app
from app.models.audio_file import AudioFile
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.summary import Summary
from app.models.task import Task
from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.summary import SummaryResult, TaskItem
from app.services.diarization import DiarizationSegment
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription.base import SegmentData, TranscriptionResult


# ==============================================================================
# 1. Testes de Idempotência em Repositórios (Transcript e Summary/Tasks)
# ==============================================================================


def test_transcript_repository_save_is_idempotent(db_session):
    """Garante que salvar transcrição repetidas vezes substitui dados sem duplicar linhas."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Idempotência Transcrição")
    repo = TranscriptRepository(db_session)

    # 1ª Tentativa de salvar transcrição
    initial_segments = [
        SegmentData(start=0.0, end=1.5, text="Primeira fala", speaker=None),
        SegmentData(start=1.5, end=3.0, text="Segunda fala", speaker=None),
    ]
    t1 = repo.save_transcript(meeting.id, "Primeira fala Segunda fala", initial_segments)
    db_session.flush()

    assert t1.content == "Primeira fala Segunda fala"
    assert len(t1.segments) == 2

    # 2ª Tentativa (reprocessamento / nova tentativa) com novos segmentos
    new_segments = [
        SegmentData(start=0.0, end=4.0, text="Texto consolidado atualizado", speaker="SPEAKER_00"),
    ]
    t2 = repo.save_transcript(meeting.id, "Texto consolidado atualizado", new_segments)
    db_session.flush()

    assert t2.id == t1.id
    assert t2.content == "Texto consolidado atualizado"

    # Verificação no banco: deve haver exatamente 1 Transcript e 1 Segment
    all_transcripts = db_session.scalars(
        select(Transcript).where(Transcript.meeting_id == meeting.id)
    ).all()
    assert len(all_transcripts) == 1

    all_segments = db_session.scalars(
        select(TranscriptSegment).where(TranscriptSegment.transcript_id == t1.id)
    ).all()
    assert len(all_segments) == 1
    assert all_segments[0].text == "Texto consolidado atualizado"


def test_transcript_repository_apply_diarization_supports_commit_flag(db_session):
    """Verifica que apply_diarization é idempotente e respeita a flag commit."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Diarização Idempotente")
    repo = TranscriptRepository(db_session)

    segments = [
        SegmentData(start=0.0, end=2.0, text="Olá mundo", speaker=None),
    ]
    transcript = repo.save_transcript(meeting.id, "Olá mundo", segments)

    diar_segments = [
        DiarizationSegment(speaker="Alice", start_time=0.0, end_time=2.0),
    ]

    # Chamada com commit=False para unidade atômica de trabalho
    updated = repo.apply_diarization(transcript, diar_segments, commit=False)
    assert updated.segments[0].speaker == "Alice"

    # Segunda chamada (idempotente)
    diar_segments_v2 = [
        DiarizationSegment(speaker="Bob", start_time=0.0, end_time=2.0),
    ]
    updated_v2 = repo.apply_diarization(transcript, diar_segments_v2, commit=True)
    assert updated_v2.segments[0].speaker == "Bob"

    all_segments = db_session.scalars(
        select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id)
    ).all()
    assert len(all_segments) == 1


def test_summary_repository_save_summary_is_idempotent(db_session):
    """Garante que save_summary e save_result substituem dados sem duplicar Summary nem Tasks."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Idempotência Resumo")
    repo = SummaryRepository(db_session)

    # 1ª Tentativa: grava summary e 2 tarefas
    s1 = repo.save_summary(
        meeting_id=meeting.id,
        objective="Objetivo 1",
        summary="Resumo inicial",
        main_points=["Ponto 1", "Ponto 2"],
        decisions=["Decisão 1"],
        tasks=[
            {"description": "Tarefa A", "responsible": "João"},
            {"description": "Tarefa B", "responsible": "Maria"},
        ],
        commit=True,
    )

    assert s1.summary == "Resumo inicial"
    assert len(meeting.tasks) == 2

    # 2ª Tentativa (retry após reprocessamento): atualiza resumo e substitui tarefas por 1 nova
    s2 = repo.save_summary(
        meeting_id=meeting.id,
        objective="Objetivo Final",
        summary="Resumo reprocessado",
        main_points=["Ponto Final"],
        decisions=["Decisão Final"],
        tasks=[
            {"description": "Tarefa Substituta", "responsible": "Carlos"},
        ],
        commit=True,
    )

    assert s2.id == s1.id
    assert s2.summary == "Resumo reprocessado"

    # Verificação no banco: exatamente 1 Summary e 1 Task
    all_summaries = db_session.scalars(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).all()
    assert len(all_summaries) == 1

    all_tasks = db_session.scalars(
        select(Task).where(Task.meeting_id == meeting.id)
    ).all()
    assert len(all_tasks) == 1
    assert all_tasks[0].description == "Tarefa Substituta"


def test_summary_repository_save_result_delegation_idempotent(db_session):
    """Garante que save_result com SummaryResult mantém total idempotência."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Idempotência save_result")
    repo = SummaryRepository(db_session)

    res1 = SummaryResult(
        objective="Obj 1",
        summary="Sum 1",
        key_points=["KP 1"],
        decisions=["Dec 1"],
        tasks=[TaskItem(description="T1", responsible="Ana")],
    )
    repo.save_result(meeting.id, res1)

    res2 = SummaryResult(
        objective="Obj 2",
        summary="Sum 2",
        key_points=["KP 2"],
        decisions=["Dec 2"],
        tasks=[TaskItem(description="T2", responsible="Bruno")],
    )
    repo.save_result(meeting.id, res2)

    all_summaries = db_session.scalars(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).all()
    assert len(all_summaries) == 1
    assert all_summaries[0].summary == "Sum 2"

    all_tasks = db_session.scalars(
        select(Task).where(Task.meeting_id == meeting.id)
    ).all()
    assert len(all_tasks) == 1
    assert all_tasks[0].description == "T2"


# ==============================================================================
# 2. Testes de Transação e Idempotência no MeetingProcessor
# ==============================================================================


def test_meeting_processor_rolls_back_partial_data_on_error(db_session, tmp_path):
    """Verifica que o MeetingProcessor faz rollback em caso de falha, não deixando dados inconsistentes."""
    meeting_repo = MeetingRepository(db_session)
    transcript_repo = TranscriptRepository(db_session)
    summary_repo = SummaryRepository(db_session)

    meeting = meeting_repo.create("Reunião Falha Transacional")
    audio = AudioFile(
        meeting_id=meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=1000,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    storage_mock = MagicMock()
    storage_mock.file_exists.return_value = True
    storage_mock.get_file_path.return_value = tmp_path / "audio.mp3"

    stt_mock = MagicMock()
    stt_mock.transcribe.return_value = TranscriptionResult(
        text="Transcrição que seria salva",
        segments=[SegmentData(start=0.0, end=2.0, text="Transcrição que seria salva", speaker=None)],
    )

    diar_mock = MagicMock()
    diar_mock.diarize.return_value = [
        DiarizationSegment(speaker="Speaker 1", start_time=0.0, end_time=2.0)
    ]

    chunk_mock = MagicMock()
    chunk_mock.split.return_value = ["chunk 1"]

    # LLM falha intencionalmente
    llm_summarizer_mock = MagicMock()
    llm_summarizer_mock.summarize.side_effect = RuntimeError("Falha definitiva no LLM")

    processor = MeetingProcessor(
        meeting_repository=meeting_repo,
        transcript_repository=transcript_repo,
        summary_repository=summary_repo,
        audio_storage_service=storage_mock,
        speech_to_text_service=stt_mock,
        diarization_service=diar_mock,
        chunking_service=chunk_mock,
        summarization_service=llm_summarizer_mock,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(RuntimeError, match="Falha definitiva no LLM"):
        processor.process_meeting(meeting.id)

    db_session.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED

    # Devido ao use_atomic_unit_of_work e db.rollback(), nada foi persistido antes da falha
    persisted_transcript = transcript_repo.get_by_meeting_id(meeting.id)
    assert persisted_transcript is None

    persisted_summary = summary_repo.get_by_meeting_id(meeting.id)
    assert persisted_summary is None


# ==============================================================================
# 3. Testes do Endpoint de Retry Manual (POST /meetings/{meeting_id}/retry)
# ==============================================================================


def test_manual_retry_success_on_failed_meeting(client, db_session, monkeypatch):
    """Verifica que POST /meetings/{id}/retry aceita reprocessamento de reunião FAILED com áudio."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Pronta para Retry", status=MeetingStatus.FAILED)

    audio = AudioFile(
        meeting_id=meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=2048,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    # Simula que o arquivo existe no storage
    monkeypatch.setattr(
        "app.services.audio_storage.AudioStorageService.file_exists",
        lambda self, path: True,
    )

    mock_enqueue = MagicMock()
    monkeypatch.setattr("app.api.v1.meetings.enqueue_meeting_processing", mock_enqueue)

    response = client.post(f"/meetings/{meeting.id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meeting.id
    assert data["status"] == MeetingStatus.PROCESSING.value

    # Confirma que o job foi enfileirado
    mock_enqueue.assert_called_once()


def test_manual_retry_blocks_not_found(client):
    """Retorna 404 para reunião inexistente."""
    response = client.post("/meetings/99999/retry")
    assert response.status_code == 404
    assert "não encontrada" in response.json()["detail"]


def test_manual_retry_blocks_missing_audio(client, db_session):
    """Retorna 422 se a reunião não possui arquivo de áudio."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Sem Áudio", status=MeetingStatus.FAILED)

    response = client.post(f"/meetings/{meeting.id}/retry")
    assert response.status_code == 422
    assert "Arquivo de áudio não encontrado" in response.json()["detail"]


def test_manual_retry_blocks_concurrent_processing(client, db_session, monkeypatch):
    """Retorna 409 se a reunião já está em processamento."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião em Execução", status=MeetingStatus.PROCESSING)

    audio = AudioFile(
        meeting_id=meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=2048,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.audio_storage.AudioStorageService.file_exists",
        lambda self, path: True,
    )

    response = client.post(f"/meetings/{meeting.id}/retry")
    assert response.status_code == 409
    assert "já está em processamento" in response.json()["detail"]


def test_manual_retry_blocks_completed_meeting(client, db_session, monkeypatch):
    """Retorna 409 se a reunião já foi concluída com sucesso."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Já Concluída", status=MeetingStatus.COMPLETED)

    audio = AudioFile(
        meeting_id=meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=2048,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.audio_storage.AudioStorageService.file_exists",
        lambda self, path: True,
    )

    response = client.post(f"/meetings/{meeting.id}/retry")
    assert response.status_code == 409
    assert "já foi processada com sucesso" in response.json()["detail"]


def test_manual_retry_blocks_non_failed_status(client, db_session, monkeypatch):
    """Retorna 409 se o status for RECEIVED (ainda não falhou)."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Received", status=MeetingStatus.RECEIVED)

    audio = AudioFile(
        meeting_id=meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=2048,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.audio_storage.AudioStorageService.file_exists",
        lambda self, path: True,
    )

    response = client.post(f"/meetings/{meeting.id}/retry")
    assert response.status_code == 409
    assert "exclusivamente a reuniões com falha" in response.json()["detail"]


# ==============================================================================
# 4. Testes do Endpoint de Processamento (POST /meetings/{meeting_id}/process)
# ==============================================================================


def test_process_endpoint_starts_pipeline(client, db_session, monkeypatch):
    """Verifica que POST /meetings/{id}/process aceita reunião com áudio pronto."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Nova", status=MeetingStatus.AUDIO_UPLOADED)

    audio = AudioFile(
        meeting_id=meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=2048,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.audio_storage.AudioStorageService.file_exists",
        lambda self, path: True,
    )

    mock_enqueue = MagicMock()
    monkeypatch.setattr("app.api.v1.meetings.enqueue_meeting_processing", mock_enqueue)

    response = client.post(f"/meetings/{meeting.id}/process")
    assert response.status_code == 200
    assert response.json()["status"] == MeetingStatus.PROCESSING.value
    mock_enqueue.assert_called_once()
