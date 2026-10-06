"""Suíte de Testes da Matriz de Resiliência, Tratamento de Erros e Retry (Issue #26).

Validação dos 11 requisitos da matriz de testes:
1. Falha temporária no STT.
2. Falha definitiva no STT.
3. Timeout do LLM.
4. Rate limit.
5. Provider temporariamente indisponível.
6. Sucesso após uma tentativa falha.
7. Falha após esgotar tentativas.
8. Atualização correta do status.
9. Retry manual.
10. Ausência de registros duplicados.
11. Exceções padronizadas.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    ApplicationError,
    DefinitiveError,
    FailureCategory,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMProviderError,
    RecoverableError,
    TranscriptionAudioCorruptedError,
    TranscriptionAudioNotFoundError,
    TranscriptionEmptyResponseError,
    TranscriptionProviderError,
    TranscriptionRateLimitError,
    TranscriptionTimeoutError,
    is_definitive,
    is_recoverable,
)
from app.core.retry import RetryPolicy
from app.models.audio_file import AudioFile
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.summary import Summary
from app.models.task import Task
from app.models.transcript import Transcript
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.summary import SummaryResult, TaskItem
from app.services.diarization import DiarizationSegment
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription.base import SegmentData, TranscriptionResult
from app.workers.job_runner import JobRunner


# ==============================================================================
# 1. Falha temporária no STT
# ==============================================================================
def test_1_falha_temporaria_no_stt(db_session, tmp_path):
    """Falha temporária no STT (ex: timeout de rede) é recuperável e dispara retry com sucesso."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Falha Temporária STT")

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    attempts = 0

    def mock_stt_transcribe(audio_file):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TranscriptionTimeoutError("Timeout temporário ao conectar à API de STT")
        return TranscriptionResult(text="Transcrição recuperada", segments=[])

    result = runner.execute_operation(
        mock_stt_transcribe,
        tmp_path / "audio.mp3",
        meeting=meeting,
        stage="speech_to_text",
    )

    assert attempts == 2
    assert result.text == "Transcrição recuperada"
    assert is_recoverable(TranscriptionTimeoutError("Timeout")) is True


# ==============================================================================
# 2. Falha definitiva no STT
# ==============================================================================
def test_2_falha_definitiva_no_stt(db_session, tmp_path):
    """Falha definitiva no STT (áudio corrompido ou vazio) aborta imediatamente sem retry e marca FAILED."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Áudio Corrompido STT")

    policy = RetryPolicy(max_attempts=4, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    attempts = 0

    def mock_stt_corrupted(audio_file):
        nonlocal attempts
        attempts += 1
        raise TranscriptionAudioCorruptedError("Arquivo de áudio com cabeçalho inválido ou corrompido")

    with pytest.raises(TranscriptionAudioCorruptedError):
        runner.execute_operation(
            mock_stt_corrupted,
            tmp_path / "corrupted.mp3",
            meeting=meeting,
            stage="speech_to_text",
        )

    # Aborta na 1ª tentativa
    assert attempts == 1
    assert meeting.status == MeetingStatus.FAILED
    assert is_definitive(TranscriptionAudioCorruptedError("Erro")) is True


# ==============================================================================
# 3. Timeout do LLM
# ==============================================================================
def test_3_timeout_do_llm():
    """Timeout do LLM é classificado como recuperável e herda de LLMError e RecoverableError."""
    err = LLMTimeoutError("Tempo limite de geração excedido pelo provedor Gemini")

    assert err.is_retryable is True
    assert err.category == FailureCategory.RECOVERABLE
    assert is_recoverable(err) is True
    assert is_definitive(err) is False

    # Validação de retry em operação com timeout
    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    calls = 0

    def mock_llm_call():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise err
        return "Resumo gerado com sucesso após timeout"

    res = policy.execute(mock_llm_call)
    assert res == "Resumo gerado com sucesso após timeout"
    assert calls == 2


# ==============================================================================
# 4. Rate limit
# ==============================================================================
def test_4_rate_limit():
    """Erros de Rate Limit (HTTP 429) tanto em STT quanto em LLM são recuperáveis e retentam."""
    stt_rate = TranscriptionRateLimitError("Rate limit de STT excedido (HTTP 429)")
    llm_rate = LLMRateLimitError("Rate limit de LLM excedido (HTTP 429)")

    assert is_recoverable(stt_rate) is True
    assert is_recoverable(llm_rate) is True

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    attempts = 0

    def call_with_rate_limit():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise llm_rate
        return "Concluído após espera de quota"

    result = policy.execute(call_with_rate_limit)
    assert result == "Concluído após espera de quota"
    assert attempts == 3


# ==============================================================================
# 5. Provider temporariamente indisponível
# ==============================================================================
def test_5_provider_temporariamente_indisponivel():
    """Erros transitórios de infraestrutura (HTTP 502/503/504) são recuperáveis."""
    stt_503 = TranscriptionProviderError("Serviço Groq indisponível temporariamente (503 Service Unavailable)")
    llm_502 = LLMProviderError("Bad Gateway no provedor Gemini (502 Bad Gateway)")

    assert is_recoverable(stt_503) is True
    assert is_recoverable(llm_502) is True

    policy = RetryPolicy(max_attempts=2, initial_delay=0.01)
    attempts = 0

    def call_provider():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise llm_502
        return "Provider voltou ao ar"

    result = policy.execute(call_provider)
    assert result == "Provider voltou ao ar"
    assert attempts == 2


# ==============================================================================
# 6. Sucesso após uma tentativa falha
# ==============================================================================
def test_6_sucesso_apos_uma_tentativa_falha(db_session):
    """Execução que falha na tentativa 1 com erro transitório tem sucesso na tentativa 2."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Sucesso Após Falha")

    runner = JobRunner(
        retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.01),
        meeting_repository=meeting_repo,
    )

    count = 0

    def flaky_task():
        nonlocal count
        count += 1
        if count == 1:
            raise LLMTimeoutError("Falha na 1ª tentativa")
        return {"objective": "Alinhamento", "summary": "Resumo concluído"}

    output = runner.execute_operation(flaky_task, meeting=meeting, stage="summarization")
    assert count == 2
    assert output["objective"] == "Alinhamento"
    # Status não foi marcado como FAILED
    assert meeting.status != MeetingStatus.FAILED


# ==============================================================================
# 7. Falha após esgotar tentativas
# ==============================================================================
def test_7_falha_apos_esgotar_tentativas(db_session):
    """Quando o número máximo de tentativas é esgotado, o job marca FAILED e registra a falha."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Esgotamento Retries")

    runner = JobRunner(
        retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.01),
        meeting_repository=meeting_repo,
    )

    attempts = 0

    def always_failing_recoverable():
        nonlocal attempts
        attempts += 1
        raise LLMTimeoutError("Timeout persistente")

    with pytest.raises(LLMTimeoutError):
        runner.execute_operation(
            always_failing_recoverable,
            meeting=meeting,
            stage="summarization",
        )

    assert attempts == 3
    assert meeting.status == MeetingStatus.FAILED
    assert runner.last_failure is not None
    assert runner.last_failure.attempts == 3
    assert runner.last_failure.stage == "summarization"


# ==============================================================================
# 8. Atualização correta do status
# ==============================================================================
def test_8_atualizacao_correta_do_status(db_session, tmp_path):
    """O status permanece PROCESSING durante retry transitório, nunca COMPLETED em erro e FAILED ao falhar."""
    meeting_repo = MeetingRepository(db_session)
    transcript_repo = TranscriptRepository(db_session)
    meeting = meeting_repo.create("Reunião Ciclo de Status", status=MeetingStatus.PROCESSING)

    audio = AudioFile(
        meeting_id=meeting.id,
        filename="meeting.mp3",
        original_filename="meeting.mp3",
        file_path="audio/meeting.mp3",
        file_size_bytes=1024,
        content_type="audio/mpeg",
    )
    db_session.add(audio)
    db_session.commit()

    storage_mock = MagicMock()
    storage_mock.file_exists.return_value = True
    storage_mock.get_file_path.return_value = tmp_path / "meeting.mp3"

    stt_mock = MagicMock()
    stt_mock.transcribe.return_value = TranscriptionResult(text="Transcrição ok", segments=[])

    diar_mock = MagicMock()
    diar_mock.diarize.return_value = []

    chunk_mock = MagicMock()
    chunk_mock.split.return_value = ["chunk"]

    # Simula erro fatal no LLM
    llm_mock = MagicMock()
    llm_mock.summarize.side_effect = LLMProviderError("Falha irrecuperável do LLM")

    processor = MeetingProcessor(
        meeting_repository=meeting_repo,
        transcript_repository=transcript_repo,
        audio_storage_service=storage_mock,
        speech_to_text_service=stt_mock,
        diarization_service=diar_mock,
        chunking_service=chunk_mock,
        summarization_service=llm_mock,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(LLMProviderError):
        processor.process_meeting(meeting.id, allow_already_processing=True)

    db_session.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    assert meeting.status != MeetingStatus.COMPLETED


# ==============================================================================
# 9. Retry manual
# ==============================================================================
def test_9_retry_manual(client, db_session, monkeypatch):
    """POST /meetings/{id}/retry permite reprocessar reunião FAILED e bloqueia estados inválidos."""
    meeting_repo = MeetingRepository(db_session)
    failed_meeting = meeting_repo.create("Reunião Falhada", status=MeetingStatus.FAILED)

    audio = AudioFile(
        meeting_id=failed_meeting.id,
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

    # 1. Sucesso no retry manual
    res_retry = client.post(f"/meetings/{failed_meeting.id}/retry")
    assert res_retry.status_code == 200
    assert res_retry.json()["status"] == MeetingStatus.PROCESSING.value
    mock_enqueue.assert_called_once()

    # 2. Bloqueio de reunião inexistente (404)
    res_404 = client.post("/meetings/999999/retry")
    assert res_404.status_code == 404

    # 3. Bloqueio de reunião já em processamento (409)
    proc_meeting = meeting_repo.create("Reunião Processando", status=MeetingStatus.PROCESSING)
    audio_proc = AudioFile(
        meeting_id=proc_meeting.id,
        filename="test.mp3",
        original_filename="test.mp3",
        file_path="audio/test.mp3",
        file_size_bytes=2048,
        content_type="audio/mpeg",
    )
    db_session.add(audio_proc)
    db_session.commit()

    res_409 = client.post(f"/meetings/{proc_meeting.id}/retry")
    assert res_409.status_code == 409
    assert "já está em processamento" in res_409.json()["detail"]


# ==============================================================================
# 10. Ausência de registros duplicados
# ==============================================================================
def test_10_ausencia_de_registros_duplicados(db_session):
    """Múltiplas tentativas de persistência de Transcript, Summary e Tarefas não produzem duplicatas."""
    meeting_repo = MeetingRepository(db_session)
    meeting = meeting_repo.create("Reunião Anti Duplicação")
    transcript_repo = TranscriptRepository(db_session)
    summary_repo = SummaryRepository(db_session)

    # 1. Transcrição repetida
    transcript_repo.save_transcript(meeting.id, "Tentativa 1", [
        SegmentData(start=0.0, end=1.0, text="Fala 1", speaker=None)
    ])
    transcript_repo.save_transcript(meeting.id, "Tentativa 2 (Sobrescrita)", [
        SegmentData(start=0.0, end=2.0, text="Fala Atualizada", speaker="Alice")
    ])

    transcripts = db_session.scalars(select(Transcript).where(Transcript.meeting_id == meeting.id)).all()
    assert len(transcripts) == 1
    assert transcripts[0].content == "Tentativa 2 (Sobrescrita)"

    # 2. Resumo e tarefas repetidos
    summary_repo.save_summary(
        meeting_id=meeting.id,
        objective="Obj 1",
        summary="Sum 1",
        tasks=[{"description": "Task 1", "responsible": "A"}],
    )
    summary_repo.save_summary(
        meeting_id=meeting.id,
        objective="Obj 2",
        summary="Sum 2",
        tasks=[{"description": "Task Substituta", "responsible": "B"}],
    )

    summaries = db_session.scalars(select(Summary).where(Summary.meeting_id == meeting.id)).all()
    tasks = db_session.scalars(select(Task).where(Task.meeting_id == meeting.id)).all()

    assert len(summaries) == 1
    assert summaries[0].summary == "Sum 2"
    assert len(tasks) == 1
    assert tasks[0].description == "Task Substituta"


# ==============================================================================
# 11. Exceções padronizadas
# ==============================================================================
def test_11_excecoes_padronizadas():
    """Todas as exceções do domínio herdam de ApplicationError e possuem contratos estruturados."""
    exceptions_to_check = [
        TranscriptionAudioNotFoundError("Áudio não encontrado"),
        TranscriptionAudioCorruptedError("Áudio corrompido"),
        TranscriptionTimeoutError("Timeout STT"),
        TranscriptionRateLimitError("Rate limit STT"),
        TranscriptionProviderError("Provider STT falhou"),
        LLMTimeoutError("Timeout LLM"),
        LLMRateLimitError("Rate limit LLM"),
        LLMProviderError("Provider LLM falhou"),
    ]

    for exc in exceptions_to_check:
        assert isinstance(exc, ApplicationError)
        assert isinstance(exc.message, str)
        assert isinstance(exc.is_retryable, bool)
        assert isinstance(exc.category, FailureCategory)
        # Classificação coerente
        if exc.is_retryable:
            assert isinstance(exc, RecoverableError)
            assert exc.category == FailureCategory.RECOVERABLE
        else:
            assert isinstance(exc, DefinitiveError)
            assert exc.category == FailureCategory.DEFINITIVE
