from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMTimeoutError,
    TranscriptionAudioCorruptedError,
    TranscriptionTimeoutError,
)
from app.core.retry import RetryPolicy
from app.models.meeting_status import MeetingStatus
from app.services.processing.meeting_processor import MeetingProcessor
from app.workers.job_runner import JobRunner


class FakeMeeting:
    def __init__(self, id: int = 1, status: MeetingStatus = MeetingStatus.AUDIO_UPLOADED):
        self.id = id
        self.status = status
        self.audio = MagicMock(file_path="audio/meeting_1.wav")


# =====================================================================
# 1. Fluxo do Job: Sucesso -> Continua
# =====================================================================
def test_job_runner_operation_success_continues():
    """Operação com sucesso prossegue a execução sem falhas."""
    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy)

    meeting = FakeMeeting()
    success_callback = MagicMock()

    result = runner.execute_operation(
        lambda x: x * 2,
        21,
        meeting=meeting,
        on_success=success_callback,
    )

    assert result == 42
    success_callback.assert_called_once_with(42)
    assert meeting.status == MeetingStatus.AUDIO_UPLOADED


# =====================================================================
# 2. Fluxo do Job: Erro Recuperável -> Retry
# =====================================================================
def test_job_runner_operation_recoverable_error_retries():
    """Erro recuperável deve sofrer retry e continuar o fluxo após recuperação."""
    attempts = 0

    def transient_op():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise LLMTimeoutError("Timeout temporário no LLM")
        return "sucesso_recuperado"

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy)
    meeting = FakeMeeting()

    result = runner.execute_operation(transient_op, meeting=meeting)

    assert result == "sucesso_recuperado"
    assert attempts == 3
    assert meeting.status == MeetingStatus.AUDIO_UPLOADED


# =====================================================================
# 3. Fluxo do Job: Erro Definitivo -> FAILED Imediato
# =====================================================================
def test_job_runner_operation_definitive_error_marks_failed():
    """Erro definitivo não sofre retry e marca a reunião como FAILED imediatamente."""
    attempts = 0

    def definitive_op():
        nonlocal attempts
        attempts += 1
        raise LLMAuthenticationError("Chave de API inválida (401)")

    meeting_repo = MagicMock()
    meeting = FakeMeeting()

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    policy = RetryPolicy(max_attempts=5, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    with pytest.raises(LLMAuthenticationError):
        runner.execute_operation(definitive_op, meeting=meeting)

    assert attempts == 1  # Aborto estrito no primeiro erro
    assert meeting.status == MeetingStatus.FAILED
    meeting_repo.update_status.assert_called_once_with(meeting, MeetingStatus.FAILED)


# =====================================================================
# 4. Fluxo do Job: Esgotamento de Tentativas -> FAILED
# =====================================================================
def test_job_runner_operation_exhausted_retries_marks_failed():
    """Quando retentativas de erro recuperável se esgotam, marca como FAILED."""
    attempts = 0

    def persistently_failing_op():
        nonlocal attempts
        attempts += 1
        raise TranscriptionTimeoutError("Timeout persistente no STT")

    meeting_repo = MagicMock()
    meeting = FakeMeeting()

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    with pytest.raises(TranscriptionTimeoutError):
        runner.execute_operation(persistently_failing_op, meeting=meeting)

    assert attempts == 3
    assert meeting.status == MeetingStatus.FAILED
    meeting_repo.update_status.assert_called_once_with(meeting, MeetingStatus.FAILED)


# =====================================================================
# 5. Fluxo Assíncrono com JobRunner
# =====================================================================
@pytest.mark.anyio
async def test_job_runner_async_operation_lifecycle():
    """Valida o ciclo de retry e transição de status no fluxo de corrotinas."""
    attempts = 0

    async def async_transient_op():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise LLMTimeoutError("Falha temporária assíncrona")
        return "async_ok"

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy)
    meeting = FakeMeeting()

    result = await runner.execute_async_operation(async_transient_op, meeting=meeting)

    assert result == "async_ok"
    assert attempts == 2
    assert meeting.status == MeetingStatus.AUDIO_UPLOADED


@pytest.mark.anyio
async def test_job_runner_async_definitive_error_marks_failed():
    """Corrotina com falha definitiva deve marcar FAILED sem novas tentativas."""
    attempts = 0

    async def async_definitive_op():
        nonlocal attempts
        attempts += 1
        raise TranscriptionAudioCorruptedError("Arquivo corrompido")

    meeting_repo = MagicMock()
    meeting = FakeMeeting()

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    policy = RetryPolicy(max_attempts=4, initial_delay=0.01)
    runner = JobRunner(retry_policy=policy, meeting_repository=meeting_repo)

    with pytest.raises(TranscriptionAudioCorruptedError):
        await runner.execute_async_operation(async_definitive_op, meeting=meeting)

    assert attempts == 1
    assert meeting.status == MeetingStatus.FAILED


# =====================================================================
# 6. Comportamento Previsível entre Providers (LLM vs STT)
# =====================================================================
def test_job_runner_predictable_behavior_across_providers():
    """Garante que provedores STT e LLM tenham tratamento simétrico no worker."""
    meeting_repo = MagicMock()
    meeting = FakeMeeting()
    runner = JobRunner(
        retry_policy=RetryPolicy(max_attempts=2, initial_delay=0.01),
        meeting_repository=meeting_repo,
    )

    # 1. Provedor STT recuperável esgotado
    with pytest.raises(TranscriptionTimeoutError):
        runner.execute_operation(
            MagicMock(side_effect=TranscriptionTimeoutError("Timeout STT")),
            meeting=meeting,
        )
    meeting_repo.update_status.assert_called_with(meeting, MeetingStatus.FAILED)

    meeting_repo.reset_mock()

    # 2. Provedor LLM definitivo
    with pytest.raises(LLMAuthenticationError):
        runner.execute_operation(
            MagicMock(side_effect=LLMAuthenticationError("401 LLM")),
            meeting=meeting,
        )
    meeting_repo.update_status.assert_called_with(meeting, MeetingStatus.FAILED)


# =====================================================================
# 7. Teste de Integração no MeetingProcessor
# =====================================================================
def test_meeting_processor_retries_transient_operation_and_completes():
    """MeetingProcessor aplica retry em falha transitória do provedor e conclui."""
    meeting = FakeMeeting()
    meeting_repo = MagicMock()
    meeting_repo.get_by_id.return_value = meeting

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    transcript_repo = MagicMock()
    transcript_repo.save_transcript.return_value = MagicMock()
    audio_storage = MagicMock()
    audio_storage.file_exists.return_value = True
    audio_storage.get_file_path.return_value = "/tmp/fake.wav"

    stt_attempts = 0

    def mock_transcribe(audio_path):
        nonlocal stt_attempts
        stt_attempts += 1
        if stt_attempts == 1:
            raise TranscriptionTimeoutError("Timeout transitório do provedor STT")
        return MagicMock(text="Transcrição recuperada", segments=[])

    stt_service = MagicMock()
    stt_service.transcribe = mock_transcribe

    diarization_service = MagicMock()
    diarization_service.diarize.return_value = []

    chunking_service = MagicMock()
    chunking_service.split.return_value = []

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    processor = MeetingProcessor(
        meeting_repository=meeting_repo,
        transcript_repository=transcript_repo,
        audio_storage_service=audio_storage,
        speech_to_text_service=stt_service,
        diarization_service=diarization_service,
        chunking_service=chunking_service,
        retry_policy=policy,
    )

    processor.process_meeting(meeting.id)

    assert stt_attempts == 2
    assert meeting.status == MeetingStatus.COMPLETED


def test_meeting_processor_marks_failed_on_definitive_error():
    """MeetingProcessor aborta imediatamente e marca FAILED em erro definitivo."""
    meeting = FakeMeeting()
    meeting_repo = MagicMock()
    meeting_repo.get_by_id.return_value = meeting

    def fake_update(m, status):
        m.status = status
        return m

    meeting_repo.update_status.side_effect = fake_update

    transcript_repo = MagicMock()
    audio_storage = MagicMock()
    audio_storage.file_exists.return_value = True
    audio_storage.get_file_path.return_value = "/tmp/fake.wav"

    stt_service = MagicMock()
    stt_service.transcribe.side_effect = TranscriptionAudioCorruptedError(
        "Arquivo corrompido"
    )

    processor = MeetingProcessor(
        meeting_repository=meeting_repo,
        transcript_repository=transcript_repo,
        audio_storage_service=audio_storage,
        speech_to_text_service=stt_service,
        diarization_service=MagicMock(),
        chunking_service=MagicMock(),
        retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.01),
    )

    with pytest.raises(TranscriptionAudioCorruptedError):
        processor.process_meeting(meeting.id)

    assert meeting.status == MeetingStatus.FAILED
    assert stt_service.transcribe.call_count == 1
