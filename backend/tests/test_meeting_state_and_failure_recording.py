from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMTimeoutError,
    TranscriptionAudioCorruptedError,
    TranscriptionTimeoutError,
)
from app.core.failure_recorder import FailureRecord, FailureRecorder, sanitize_error_message
from app.core.retry import RetryPolicy
from app.models.meeting_status import MeetingStatus
from app.services.processing.meeting_processor import MeetingProcessor
from app.workers.job_runner import JobRunner


class FakeMeeting:
    def __init__(self, id: int = 1, status: MeetingStatus = MeetingStatus.PROCESSING):
        self.id = id
        self.status = status
        self.audio = MagicMock(file_path="audio/meeting_test.wav")


# =====================================================================
# Item 8: Atualizar estado da reunião corretamente
# =====================================================================
def test_meeting_state_remains_processing_during_retries():
    """Durante retries, o estado da reunião não se altera e permanece PROCESSING."""
    attempts = 0
    statuses_during_retries = []

    meeting = FakeMeeting(status=MeetingStatus.PROCESSING)
    meeting_repo = MagicMock()

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    def transient_op():
        nonlocal attempts
        attempts += 1
        # Captura status do meeting durante a execução da tentativa
        statuses_during_retries.append(meeting.status)
        if attempts < 3:
            raise LLMTimeoutError("Falha transitória na chamada")
        return "recuperado"

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    result = runner.execute_operation(transient_op, meeting=meeting, stage="llm_call")

    assert result == "recuperado"
    assert attempts == 3
    # Nenhuma tentativa viu status FAILED; manteve-se consistente em PROCESSING
    assert all(st == MeetingStatus.PROCESSING for st in statuses_during_retries)
    assert meeting.status == MeetingStatus.PROCESSING
    meeting_repo.update_status.assert_not_called()


def test_meeting_state_marked_failed_when_all_attempts_exhausted():
    """Somente após o esgotamento de todas as tentativas a reunião vira FAILED."""
    attempts = 0
    meeting = FakeMeeting(status=MeetingStatus.PROCESSING)
    meeting_repo = MagicMock()

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    def always_failing():
        nonlocal attempts
        attempts += 1
        raise TranscriptionTimeoutError("Timeout ininterrupto")

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    with pytest.raises(TranscriptionTimeoutError):
        runner.execute_operation(always_failing, meeting=meeting, stage="speech_to_text")

    assert attempts == 3
    assert meeting.status == MeetingStatus.FAILED
    meeting_repo.update_status.assert_called_once_with(meeting, MeetingStatus.FAILED)


def test_meeting_state_marked_failed_immediately_on_definitive_error():
    """Falha definitiva marca FAILED na 1ª tentativa sem novas tentativas."""
    attempts = 0
    meeting = FakeMeeting(status=MeetingStatus.PROCESSING)
    meeting_repo = MagicMock()

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    def definitive_fail():
        nonlocal attempts
        attempts += 1
        raise LLMAuthenticationError("Chave 401 inválida")

    policy = RetryPolicy(max_attempts=5, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    with pytest.raises(LLMAuthenticationError):
        runner.execute_operation(definitive_fail, meeting=meeting, stage="summarization")

    assert attempts == 1
    assert meeting.status == MeetingStatus.FAILED
    meeting_repo.update_status.assert_called_once_with(meeting, MeetingStatus.FAILED)


def test_meeting_state_never_completed_when_required_stage_fails():
    """Evitar COMPLETED quando uma etapa obrigatória falhar."""
    meeting = FakeMeeting(status=MeetingStatus.AUDIO_UPLOADED)
    meeting_repo = MagicMock()
    meeting_repo.get_by_id.return_value = meeting

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    transcript_repo = MagicMock()
    audio_storage = MagicMock()
    audio_storage.file_exists.return_value = True
    audio_storage.get_file_path.return_value = "/tmp/meeting.wav"

    # STT sucede
    stt_service = MagicMock()
    stt_service.transcribe.return_value = MagicMock(text="Texto transcrito", segments=[])

    # Diarização sucede
    diarization_service = MagicMock()
    diarization_service.diarize.return_value = []

    # Chunking falha (etapa obrigatória)
    chunking_service = MagicMock()
    chunking_service.split.side_effect = RuntimeError("Erro crítico no chunking")

    processor = MeetingProcessor(
        meeting_repository=meeting_repo,
        transcript_repository=transcript_repo,
        audio_storage_service=audio_storage,
        speech_to_text_service=stt_service,
        diarization_service=diarization_service,
        chunking_service=chunking_service,
        retry_policy=RetryPolicy(max_attempts=2, initial_delay=0.01),
    )

    with pytest.raises(RuntimeError, match="Erro crítico no chunking"):
        processor.process_meeting(meeting.id)

    # Reunião nunca foi marcada como COMPLETED; terminou como FAILED
    assert meeting.status == MeetingStatus.FAILED
    assert meeting_repo.update_status.call_args_list[-1][0][1] == MeetingStatus.FAILED


# =====================================================================
# Item 9: Registrar informações sobre falhas
# =====================================================================
def test_sanitize_error_message_redacts_api_keys_and_tokens():
    """Evita exposição de informações sensíveis (API keys, tokens, credenciais)."""
    raw_message = (
        "Falha ao conectar com api_key=gsk_1234567890abcdef1234567890 "
        "e Google Key AIzaSyD12345678901234567890123456789012. "
        "Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token e secret: secret_pass123"
    )

    cleaned = sanitize_error_message(raw_message)

    assert "gsk_1234567890abcdef1234567890" not in cleaned
    assert "AIzaSyD12345678901234567890123456789012" not in cleaned
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in cleaned
    assert "secret_pass123" not in cleaned
    assert "[REDACTED]" in cleaned


def test_failure_recorder_captures_minimal_context():
    """Registra contexto mínimo: etapa, tipo, mensagem resumida, tentativas e horário."""
    exc = TranscriptionAudioCorruptedError(
        "Áudio inválido com token secreto: gsk_supersecretkey1234567"
    )

    record = FailureRecorder.record_failure(
        stage="speech_to_text",
        error=exc,
        attempts=3,
    )

    assert isinstance(record, FailureRecord)
    assert record.stage == "speech_to_text"
    assert record.error_type == "TranscriptionAudioCorruptedError"
    assert "gsk_supersecretkey1234567" not in record.message
    assert "[REDACTED]" in record.message
    assert record.attempts == 3
    assert record.timestamp is not None
    assert record.is_recoverable is False

    as_dict = record.to_dict()
    assert as_dict["stage"] == "speech_to_text"
    assert as_dict["attempts"] == 3


def test_job_runner_records_failure_identifying_stage_and_attempts():
    """Permite identificar em qual etapa o pipeline falhou com tentativas exatas."""
    meeting = FakeMeeting(status=MeetingStatus.PROCESSING)
    meeting_repo = MagicMock()
    runner = JobRunner(
        retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.01),
        meeting_repository=meeting_repo,
    )

    attempts = 0

    def failing_diarization():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Falha interna de memória no modelo")

    with pytest.raises(RuntimeError):
        runner.execute_operation(
            failing_diarization,
            meeting=meeting,
            stage="diarization",
        )

    assert runner.last_failure is not None
    assert runner.last_failure.stage == "diarization"
    assert runner.last_failure.error_type == "RuntimeError"
    assert runner.last_failure.attempts == 1  # RuntimeError não é recuperável -> 1 tentativa
    assert runner.last_failure.is_recoverable is False
    assert meeting.status == MeetingStatus.FAILED
