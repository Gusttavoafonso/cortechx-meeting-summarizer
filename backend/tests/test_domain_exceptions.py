"""Testes unitários para padronização de exceções de domínio e retry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.core.exceptions import (
    ApplicationError,
    AudioNotFoundError,
    ChunkingError,
    DatabaseError,
    DiarizationAssociationError,
    DiarizationAudioNotFoundError,
    DiarizationConfigurationError,
    DiarizationEmptyResponseError,
    DiarizationError,
    DiarizationProviderError,
    EntityConflictError,
    EntityNotFoundError,
    InvalidPersistenceDataError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    MeetingNotFoundError,
    PersistenceError,
    ProcessingError,
    SummarizationChunkProcessingError,
    SummarizationConsolidationError,
    SummarizationEmptyInputError,
    SummarizationError,
    SummarizationInvalidResponseError,
    SummaryAlreadyProcessingError,
    SummaryNotFoundError,
    TaskExtractionError,
    TaskExtractionInvalidResponseError,
    TaskExtractionLLMFailureError,
    TranscriptionAudioCorruptedError,
    TranscriptionAudioNotFoundError,
    TranscriptionEmptyResponseError,
    TranscriptionError,
    TranscriptionProviderError,
    TranscriptionRateLimitError,
    TranscriptionTimeoutError,
    TranscriptNotFoundError,
)
from app.services.diarization import PyannoteDiarizationProvider
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.summarization.service import SummarizationService
from app.services.transcription.groq_whisper_service import GroqWhisperService
from google.genai import errors as google_errors


# =====================================================================
# 1. Testes de Hierarquia de Herança
# =====================================================================
def test_all_domain_exceptions_inherit_from_application_error():
    """Valida se todas as 5 categorias raízes herdam de ApplicationError."""
    assert issubclass(TranscriptionError, ApplicationError)
    assert issubclass(DiarizationError, ApplicationError)
    assert issubclass(LLMError, ApplicationError)
    assert issubclass(PersistenceError, ApplicationError)
    assert issubclass(ProcessingError, ApplicationError)


def test_transcription_hierarchy():
    """Valida hierarquia do ramo Transcription."""
    subclasses = [
        TranscriptionAudioNotFoundError,
        TranscriptionAudioCorruptedError,
        TranscriptionEmptyResponseError,
        TranscriptionTimeoutError,
        TranscriptionRateLimitError,
        TranscriptionProviderError,
    ]
    for cls in subclasses:
        assert issubclass(cls, TranscriptionError)
        assert issubclass(cls, ApplicationError)

    # Compatibilidade com built-in
    assert issubclass(TranscriptionAudioNotFoundError, FileNotFoundError)


def test_diarization_hierarchy():
    """Valida hierarquia do ramo Diarization."""
    subclasses = [
        DiarizationConfigurationError,
        DiarizationAudioNotFoundError,
        DiarizationEmptyResponseError,
        DiarizationAssociationError,
        DiarizationProviderError,
    ]
    for cls in subclasses:
        assert issubclass(cls, DiarizationError)
        assert issubclass(cls, ApplicationError)

    assert issubclass(DiarizationAudioNotFoundError, FileNotFoundError)


def test_llm_hierarchy():
    """Valida hierarquia do ramo LLM."""
    subclasses = [
        LLMConfigurationError,
        LLMAuthenticationError,
        LLMTimeoutError,
        LLMEmptyResponseError,
        LLMProviderError,
        LLMRateLimitError,
    ]
    for cls in subclasses:
        assert issubclass(cls, LLMError)
        assert issubclass(cls, ApplicationError)

    assert issubclass(LLMRateLimitError, LLMProviderError)


def test_persistence_hierarchy():
    """Valida hierarquia do ramo Persistence."""
    assert issubclass(EntityNotFoundError, PersistenceError)
    assert issubclass(EntityConflictError, PersistenceError)
    assert issubclass(DatabaseError, PersistenceError)
    assert issubclass(InvalidPersistenceDataError, PersistenceError)

    assert issubclass(MeetingNotFoundError, EntityNotFoundError)
    assert issubclass(TranscriptNotFoundError, EntityNotFoundError)
    assert issubclass(AudioNotFoundError, EntityNotFoundError)
    assert issubclass(SummaryNotFoundError, EntityNotFoundError)
    assert issubclass(SummaryAlreadyProcessingError, EntityConflictError)


def test_processing_hierarchy():
    """Valida hierarquia do ramo Processing."""
    assert issubclass(ChunkingError, ProcessingError)
    assert issubclass(SummarizationError, ProcessingError)
    assert issubclass(TaskExtractionError, ProcessingError)

    assert issubclass(SummarizationEmptyInputError, SummarizationError)
    assert issubclass(SummarizationChunkProcessingError, SummarizationError)
    assert issubclass(SummarizationConsolidationError, SummarizationError)
    assert issubclass(SummarizationInvalidResponseError, SummarizationError)

    assert issubclass(TaskExtractionInvalidResponseError, TaskExtractionError)
    assert issubclass(TaskExtractionLLMFailureError, TaskExtractionError)

    # Compatibilidade com built-ins
    assert issubclass(SummarizationError, RuntimeError)
    assert issubclass(SummarizationEmptyInputError, ValueError)
    assert issubclass(SummarizationInvalidResponseError, ValueError)


# =====================================================================
# 2. Testes de Classificação: Transitórias (Retryable) vs Definitivas
# =====================================================================
def test_transient_retryable_exceptions():
    """Garante que falhas temporárias sejam marcadas com retryable."""
    assert TranscriptionTimeoutError().is_retryable is True
    assert TranscriptionRateLimitError().is_retryable is True
    assert TranscriptionProviderError().is_retryable is True
    assert LLMTimeoutError().is_retryable is True
    assert LLMRateLimitError().is_retryable is True
    assert LLMProviderError().is_retryable is True
    assert TaskExtractionLLMFailureError().is_retryable is True


def test_permanent_non_retryable_exceptions():
    """Garante que falhas estruturais e definitivas NÃO sejam marcadas para retry."""
    assert ApplicationError().is_retryable is False
    assert TranscriptionAudioNotFoundError().is_retryable is False
    assert TranscriptionAudioCorruptedError().is_retryable is False
    assert TranscriptionEmptyResponseError().is_retryable is False
    assert DiarizationConfigurationError().is_retryable is False
    assert DiarizationAssociationError().is_retryable is False
    assert LLMConfigurationError().is_retryable is False
    assert LLMAuthenticationError().is_retryable is False
    assert LLMEmptyResponseError().is_retryable is False
    assert MeetingNotFoundError().is_retryable is False
    assert TranscriptNotFoundError().is_retryable is False
    assert SummaryAlreadyProcessingError().is_retryable is False
    assert ChunkingError().is_retryable is False
    assert SummarizationEmptyInputError().is_retryable is False
    assert SummarizationInvalidResponseError().is_retryable is False
    assert TaskExtractionInvalidResponseError().is_retryable is False


def test_exception_instantiation_with_custom_attributes():
    """Valida instanciação com mensagem, flag de retry customizada e detalhes."""
    err = ApplicationError(
        "Mensagem de teste", is_retryable=True, details={"code": 123}
    )
    assert str(err) == "Mensagem de teste"
    assert err.is_retryable is True
    assert err.details == {"code": 123}


# =====================================================================
# 3. Testes de Encapsulamento de Erros dos Providers
# =====================================================================
def make_google_error(error_cls, code: int, message: str = "erro simulado"):
    exc = error_cls.__new__(error_cls)
    exc.code = code
    exc.message = message
    return exc


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_maps_rate_limit(mock_client_cls):
    """Garante que HTTP 429 da API Gemini seja encapsulado em LLMRateLimitError."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = make_google_error(
        google_errors.ClientError, code=429, message="Quota exceeded"
    )
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake", model="gemini-1.5-flash")

    with pytest.raises(LLMRateLimitError) as exc_info:
        provider.generate("prompt")

    assert exc_info.value.is_retryable is True
    assert isinstance(exc_info.value, LLMProviderError)


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_maps_server_error(mock_client_cls):
    """Garante que 500 do servidor Gemini seja encapsulado com is_retryable=True."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = make_google_error(
        google_errors.ServerError, code=500, message="Internal Server Error"
    )
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake", model="gemini-1.5-flash")

    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate("prompt")

    assert exc_info.value.is_retryable is True


def test_groq_whisper_encapsulates_rate_limit():
    """Garante que rate limit no Groq é encapsulado em TranscriptionRateLimitError."""
    exc = Exception("Error: 429 rate_limit_exceeded")
    with pytest.raises(TranscriptionRateLimitError) as exc_info:
        GroqWhisperService._handle_groq_exception(exc)

    assert exc_info.value.is_retryable is True


def test_groq_whisper_encapsulates_timeout():
    """Garante que timeout no Groq é encapsulado em TranscriptionTimeoutError."""
    exc = Exception("Connection timed out after 30 seconds")
    with pytest.raises(TranscriptionTimeoutError) as exc_info:
        GroqWhisperService._handle_groq_exception(exc)

    assert exc_info.value.is_retryable is True


def test_groq_whisper_encapsulates_corrupted_audio():
    """Garante que formato ilegível vire TranscriptionAudioCorruptedError."""
    exc = Exception("Could not find codec or corrupt file")
    with pytest.raises(TranscriptionAudioCorruptedError) as exc_info:
        GroqWhisperService._handle_groq_exception(exc)

    assert exc_info.value.is_retryable is False


def test_pyannote_provider_raises_diarization_configuration_error(monkeypatch):
    """Garante que token HuggingFace ausente gera DiarizationConfigurationError."""
    monkeypatch.setattr("app.core.config.settings.huggingface_token", None)
    provider = PyannoteDiarizationProvider()

    with pytest.raises(DiarizationConfigurationError):
        provider._get_configured_token()


def test_summarization_service_raises_domain_empty_input():
    """Garante que SummarizationService lance SummarizationEmptyInputError."""
    service = SummarizationService(llm=MagicMock(), chunker=MagicMock())

    with pytest.raises(SummarizationEmptyInputError):
        service.summarize("")

    with pytest.raises(ValueError):
        service.summarize("   ")
