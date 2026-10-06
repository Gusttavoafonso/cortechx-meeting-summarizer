"""Testes unitários para a política de retry (Issue #26 - Etapa 3)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from app.core.exceptions import (
    LLMAuthenticationError,
    LLMTimeoutError,
    TranscriptionAudioCorruptedError,
    TranscriptionRateLimitError,
    TranscriptionTimeoutError,
)
from app.core.retry import RetryPolicy, retry
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.transcription.groq_whisper_service import GroqWhisperService


# =====================================================================
# 1. Definição do Número Máximo de Tentativas e Validação
# =====================================================================
def test_retry_policy_default_values():
    """Valida valores padrão da política de retry."""
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.initial_delay == 1.0
    assert policy.backoff_factor == 2.0
    assert policy.max_delay == 10.0
    assert policy.jitter is False


def test_retry_policy_invalid_parameters():
    """Valida que parâmetros inválidos disparam ValueError."""
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)

    with pytest.raises(ValueError, match="initial_delay"):
        RetryPolicy(initial_delay=-0.5)

    with pytest.raises(ValueError, match="backoff_factor"):
        RetryPolicy(backoff_factor=0.9)

    with pytest.raises(ValueError, match="max_delay"):
        RetryPolicy(initial_delay=5.0, max_delay=2.0)


# =====================================================================
# 2. Definição de Intervalo Entre Tentativas (Backoff e Jitter)
# =====================================================================
def test_calculate_delay_exponential_growth():
    """Garante progressão geométrica do intervalo até o teto max_delay."""
    policy = RetryPolicy(
        initial_delay=1.0,
        backoff_factor=2.0,
        max_delay=10.0,
        jitter=False,
    )
    assert policy.calculate_delay(1) == 1.0
    assert policy.calculate_delay(2) == 2.0
    assert policy.calculate_delay(3) == 4.0
    assert policy.calculate_delay(4) == 8.0
    assert policy.calculate_delay(5) == 10.0  # Limitado por max_delay
    assert policy.calculate_delay(6) == 10.0


def test_calculate_delay_with_jitter():
    """Com jitter ativo, o delay calculado deve ficar entre [base, 1.5 * base]."""
    policy = RetryPolicy(
        initial_delay=2.0,
        backoff_factor=2.0,
        max_delay=20.0,
        jitter=True,
    )
    for _ in range(20):
        delay = policy.calculate_delay(1)
        assert 2.0 <= delay <= 3.01


# =====================================================================
# 3. Retry Somente para Erros Recuperáveis vs Aborto em Definitivos
# =====================================================================
def test_retry_recovers_after_transient_failure():
    """Operação com falha recuperável na tentativa 1 deve ter sucesso na tentativa 2."""
    call_count = 0
    delays_recorded = []

    def transient_operation():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMTimeoutError("Timeout temporário")
        return "sucesso_recuperado"

    def record_retry(exc, attempt, delay):
        delays_recorded.append((attempt, delay))

    policy = RetryPolicy(
        max_attempts=3,
        initial_delay=0.1,
        on_retry=record_retry,
    )
    result = policy.execute(transient_operation)

    assert result == "sucesso_recuperado"
    assert call_count == 2
    assert len(delays_recorded) == 1
    assert delays_recorded[0][0] == 1


def test_retry_aborts_immediately_on_definitive_error():
    """Erro definitivo deve abortar na 1ª tentativa sem novas chamadas nem espera."""
    call_count = 0
    on_retry_called = False

    def failing_with_definitive():
        nonlocal call_count
        call_count += 1
        raise LLMAuthenticationError("Chave de API inválida (401)")

    def record_retry(exc, attempt, delay):
        nonlocal on_retry_called
        on_retry_called = True

    policy = RetryPolicy(max_attempts=5, on_retry=record_retry)

    with pytest.raises(LLMAuthenticationError):
        policy.execute(failing_with_definitive)

    assert call_count == 1
    assert on_retry_called is False


def test_retry_aborts_on_definitive_with_recoverable_cause():
    """Erro definitivo encapsulando causa recuperável não deve ser retentado."""
    call_count = 0

    def failing_with_wrapped_cause():
        nonlocal call_count
        call_count += 1
        err = TranscriptionAudioCorruptedError("Arquivo ilegível")
        err.__cause__ = TimeoutError("socket timeout interno")
        raise err

    policy = RetryPolicy(max_attempts=3)

    with pytest.raises(TranscriptionAudioCorruptedError):
        policy.execute(failing_with_wrapped_cause)

    assert call_count == 1


# =====================================================================
# 4. Impedimento de Loop Infinito (Exaustão de Tentativas)
# =====================================================================
def test_retry_prevents_infinite_loop_and_re_raises():
    """Garante que a política não entra em loop infinito e re-lança ao esgotar."""
    call_count = 0
    retries_recorded = []

    def always_failing_operation():
        nonlocal call_count
        call_count += 1
        raise TranscriptionRateLimitError("Quota 429 persistente")

    def on_retry(exc, attempt, delay):
        retries_recorded.append(attempt)

    policy = RetryPolicy(max_attempts=3, on_retry=on_retry)

    with pytest.raises(TranscriptionRateLimitError) as exc_info:
        policy.execute(always_failing_operation)

    assert call_count == 3
    assert retries_recorded == [1, 2]
    assert "Quota 429 persistente" in str(exc_info.value)


# =====================================================================
# 5. Configurabilidade (Config, Construtor e Decorador @retry)
# =====================================================================
def test_retry_policy_from_settings(monkeypatch):
    """Garante que a política carrega parâmetros configurados no Settings."""
    dummy_settings = type(
        "DummySettings",
        (),
        {
            "RETRY_MAX_ATTEMPTS": 5,
            "RETRY_INITIAL_DELAY": 0.5,
            "RETRY_BACKOFF_FACTOR": 3.0,
            "RETRY_MAX_DELAY": 15.0,
            "RETRY_JITTER": True,
        },
    )()

    policy = RetryPolicy.from_settings(dummy_settings)
    assert policy.max_attempts == 5
    assert policy.initial_delay == 0.5
    assert policy.backoff_factor == 3.0
    assert policy.max_delay == 15.0
    assert policy.jitter is True


def test_retry_decorator_sync_function():
    """Valida o decorador @retry em função síncrona."""
    calls = 0

    @retry(max_attempts=2, initial_delay=0.01)
    def my_service(param: str) -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise LLMTimeoutError("Falha temporária")
        return f"processado: {param}"

    result = my_service("dados")
    assert result == "processado: dados"
    assert calls == 2


@pytest.mark.anyio
async def test_retry_decorator_async_function():
    """Valida o decorador @retry em função assíncrona (corrotina)."""
    calls = 0

    @retry(max_attempts=3, initial_delay=0.01)
    async def my_async_service(param: str) -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TranscriptionTimeoutError("Timeout em async")
        return f"async_ok: {param}"

    result = await my_async_service("payload")
    assert result == "async_ok: payload"
    assert calls == 3


# =====================================================================
# 6. Operações Elegíveis: Provedores Gemini e Groq
# =====================================================================
def test_gemini_provider_retries_transient_and_succeeds(monkeypatch):
    """Garante que GeminiProvider aplique retry em erros 429 recuperáveis."""
    from google.genai import errors as google_errors

    client_mock = MagicMock()
    attempts = 0

    def mock_generate_content(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            err = google_errors.ClientError.__new__(google_errors.ClientError)
            err.code = 429
            err.message = "Rate limit"
            raise err
        return MagicMock(text="Resposta pós-retry")

    client_mock.models.generate_content = mock_generate_content
    monkeypatch.setattr(
        "app.services.llm.providers.gemini_provider.genai.Client",
        lambda *args, **kwargs: client_mock,
    )

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    provider = GeminiProvider(
        api_key="fake", model="gemini-1.5-flash", retry_policy=policy
    )
    result = provider.generate("prompt")

    assert result == "Resposta pós-retry"
    assert attempts == 2


def test_gemini_provider_aborts_immediately_on_401(monkeypatch):
    """Garante que GeminiProvider aborte sem retries em erro de autenticação 401."""
    from google.genai import errors as google_errors

    client_mock = MagicMock()
    attempts = 0

    def mock_generate_content(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        err = google_errors.ClientError.__new__(google_errors.ClientError)
        err.code = 401
        err.message = "Invalid API Key"
        raise err

    client_mock.models.generate_content = mock_generate_content
    monkeypatch.setattr(
        "app.services.llm.providers.gemini_provider.genai.Client",
        lambda *args, **kwargs: client_mock,
    )

    policy = RetryPolicy(max_attempts=5, initial_delay=0.01)
    provider = GeminiProvider(
        api_key="fake", model="gemini-1.5-flash", retry_policy=policy
    )

    with pytest.raises(LLMAuthenticationError):
        provider.generate("prompt")

    assert attempts == 1


def test_groq_whisper_retries_transient_and_rewinds_file():
    """Garante que GroqWhisperService aplique retry e rebobine o arquivo."""
    groq_service = GroqWhisperService(api_key="fake_groq_key")
    attempts = 0

    fake_file = io.BytesIO(b"audio-bytes-content")

    def mock_request(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        # Lê o arquivo para simular stream consumido
        fake_file.read()
        if attempts == 1:
            raise TranscriptionRateLimitError("Rate limit 429 na Groq")
        return {"text": "Transcrito com sucesso", "segments": []}

    policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
    groq_service.retry_policy = policy
    groq_service._execute_groq_request = mock_request

    response = groq_service._call_groq_api(
        file_tuple=("audio.wav", fake_file), language="pt"
    )

    assert response["text"] == "Transcrito com sucesso"
    assert attempts == 2
    assert fake_file.tell() > 0  # Rebobinado e lido novamente
