"""Testes para classificação de falhas (recuperáveis vs definitivas) - Issue #26."""

from __future__ import annotations

import pytest
from app.core.exceptions import (
    ApplicationError,
    AudioNotFoundError,
    ChunkingError,
    DatabaseError,
    DefinitiveError,
    DiarizationAssociationError,
    DiarizationAudioNotFoundError,
    DiarizationConfigurationError,
    DiarizationEmptyResponseError,
    DiarizationProviderError,
    EntityConflictError,
    EntityNotFoundError,
    FailureCategory,
    InvalidPersistenceDataError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    MeetingNotFoundError,
    PersistenceError,
    RecoverableError,
    SummarizationChunkProcessingError,
    SummarizationConsolidationError,
    SummarizationEmptyInputError,
    SummarizationError,
    SummarizationInvalidResponseError,
    SummaryAlreadyProcessingError,
    SummaryNotFoundError,
    TaskExtractionInvalidResponseError,
    TaskExtractionLLMFailureError,
    TranscriptionAudioCorruptedError,
    TranscriptionAudioNotFoundError,
    TranscriptionEmptyResponseError,
    TranscriptionProviderError,
    TranscriptionRateLimitError,
    TranscriptionTimeoutError,
    TranscriptNotFoundError,
    classify_failure,
    is_definitive,
    is_recoverable,
)


# =====================================================================
# 1. Testes de Enum e Categorias Base
# =====================================================================
def test_failure_category_enum_values():
    """Valida valores do enum de categoria de falha."""
    assert FailureCategory.RECOVERABLE == "recoverable"
    assert FailureCategory.DEFINITIVE == "definitive"


def test_recoverable_and_definitive_base_classes():
    """Valida as classes base RecoverableError e DefinitiveError."""
    rec = RecoverableError("falha temporária")
    assert rec.is_retryable is True
    assert rec.category == FailureCategory.RECOVERABLE
    assert issubclass(RecoverableError, ApplicationError)
    assert is_recoverable(rec) is True
    assert is_definitive(rec) is False
    assert classify_failure(rec) == FailureCategory.RECOVERABLE

    defe = DefinitiveError("falha definitiva")
    assert defe.is_retryable is False
    assert defe.category == FailureCategory.DEFINITIVE
    assert issubclass(DefinitiveError, ApplicationError)
    assert is_recoverable(defe) is False
    assert is_definitive(defe) is True
    assert classify_failure(defe) == FailureCategory.DEFINITIVE


# =====================================================================
# 2. Testes de Exceções de Domínio - Recuperáveis (Retryable)
# =====================================================================
@pytest.mark.parametrize(
    "exc_cls",
    [
        TranscriptionTimeoutError,
        TranscriptionRateLimitError,
        TranscriptionProviderError,
        LLMTimeoutError,
        LLMProviderError,
        LLMRateLimitError,
        TaskExtractionLLMFailureError,
    ],
)
def test_recoverable_domain_exceptions(exc_cls):
    """Garante que todas as falhas transitórias mapeiam para RECOVERABLE."""
    err = exc_cls("erro recuperável")
    assert issubclass(exc_cls, RecoverableError)
    assert err.is_retryable is True
    assert err.category == FailureCategory.RECOVERABLE
    assert is_recoverable(err) is True
    assert is_definitive(err) is False
    assert classify_failure(err) == FailureCategory.RECOVERABLE


# =====================================================================
# 3. Testes de Exceções de Domínio - Definitivas (Non-Retryable)
# =====================================================================
@pytest.mark.parametrize(
    "exc_cls",
    [
        # STT
        TranscriptionAudioNotFoundError,
        TranscriptionAudioCorruptedError,
        TranscriptionEmptyResponseError,
        # Diarization
        DiarizationConfigurationError,
        DiarizationAudioNotFoundError,
        DiarizationEmptyResponseError,
        DiarizationAssociationError,
        DiarizationProviderError,
        # LLM
        LLMConfigurationError,
        LLMAuthenticationError,
        LLMEmptyResponseError,
        # Persistence
        PersistenceError,
        EntityNotFoundError,
        MeetingNotFoundError,
        TranscriptNotFoundError,
        AudioNotFoundError,
        SummaryNotFoundError,
        EntityConflictError,
        SummaryAlreadyProcessingError,
        DatabaseError,
        InvalidPersistenceDataError,
        # Processing
        ChunkingError,
        SummarizationError,
        SummarizationEmptyInputError,
        SummarizationChunkProcessingError,
        SummarizationConsolidationError,
        SummarizationInvalidResponseError,
        TaskExtractionInvalidResponseError,
    ],
)
def test_definitive_domain_exceptions(exc_cls):
    """Garante que falhas permanentes herdem de DefinitiveError e abortem retry."""
    err = exc_cls("erro definitivo")
    assert issubclass(exc_cls, DefinitiveError)
    assert err.is_retryable is False
    assert err.category == FailureCategory.DEFINITIVE
    assert is_recoverable(err) is False
    assert is_definitive(err) is True
    assert classify_failure(err) == FailureCategory.DEFINITIVE


# =====================================================================
# 4. Critério Estrito: Erros Definitivos NUNCA Devem Sofrer Retry
# =====================================================================
def test_definitive_error_with_recoverable_cause_strictly_aborts():
    """Garante que erro definitivo com causa transitória encapsulada NÃO sofra retry.

    Exemplo: Arquivo corrompido que gerou um timeout de leitura interno não
    deve sofrer retry de ponta a ponta.
    """
    cause = TimeoutError("socket timeout interno")
    err = TranscriptionAudioCorruptedError("áudio inválido")
    err.__cause__ = cause

    assert is_recoverable(err) is False
    assert is_definitive(err) is True
    assert classify_failure(err) == FailureCategory.DEFINITIVE


# =====================================================================
# 5. Testes de Falhas Externas e Códigos HTTP
# =====================================================================
class DummyHttpError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP error {status_code}")
        self.status_code = status_code


class DummyNestedResponseError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"Response error {status_code}")
        self.response = type("Resp", (), {"status_code": status_code})()


class DummyGrpcCodeError(Exception):
    def __init__(self, code: str):
        super().__init__(f"gRPC error: {code}")
        self.code = code


@pytest.mark.parametrize("status_code", [429, 502, 503, 504])
def test_recoverable_http_status_codes(status_code):
    """HTTP 429, 502, 503 e 504 devem ser classificados como recuperáveis."""
    err1 = DummyHttpError(status_code)
    assert is_recoverable(err1) is True
    assert classify_failure(err1) == FailureCategory.RECOVERABLE

    err2 = DummyNestedResponseError(status_code)
    assert is_recoverable(err2) is True
    assert classify_failure(err2) == FailureCategory.RECOVERABLE


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 422])
def test_definitive_http_status_codes(status_code):
    """Erros de cliente (400, 401, 403, 404, 422) devem ser definitivos."""
    err1 = DummyHttpError(status_code)
    assert is_recoverable(err1) is False
    assert is_definitive(err1) is True
    assert classify_failure(err1) == FailureCategory.DEFINITIVE

    err2 = DummyNestedResponseError(status_code)
    assert is_recoverable(err2) is False
    assert is_definitive(err2) is True
    assert classify_failure(err2) == FailureCategory.DEFINITIVE


@pytest.mark.parametrize(
    "code", ["RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED"]
)
def test_recoverable_grpc_codes(code):
    """Códigos de serviço gRPC/Google temporários devem ser recuperáveis."""
    err = DummyGrpcCodeError(code)
    assert is_recoverable(err) is True
    assert classify_failure(err) == FailureCategory.RECOVERABLE


@pytest.mark.parametrize(
    "code", ["INVALID_ARGUMENT", "NOT_FOUND", "PERMISSION_DENIED", "UNAUTHENTICATED"]
)
def test_definitive_grpc_codes(code):
    """Códigos definitivos de serviço gRPC/Google devem abortar sem retry."""
    err = DummyGrpcCodeError(code)
    assert is_recoverable(err) is False
    assert is_definitive(err) is True
    assert classify_failure(err) == FailureCategory.DEFINITIVE


# =====================================================================
# 6. Testes com Exceções Nativas do Python (Built-ins)
# =====================================================================
@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timeout de operação"),
        ConnectionError("conexão resetada"),
        ConnectionResetError("peer reset connection"),
        ConnectionRefusedError("porta fechada"),
    ],
)
def test_recoverable_builtin_exceptions(exc):
    """Timeouts e erros de conexão nativos do Python são recuperáveis."""
    assert is_recoverable(exc) is True
    assert classify_failure(exc) == FailureCategory.RECOVERABLE


@pytest.mark.parametrize(
    "exc",
    [
        FileNotFoundError("áudio não encontrado"),
        ValueError("formato incorreto"),
        TypeError("tipo de parâmetro inválido"),
        KeyError("chave ausente"),
        AttributeError("atributo ausente"),
        PermissionError("permissão negada"),
    ],
)
def test_definitive_builtin_exceptions(exc):
    """Erros de sintaxe, formato, dados e arquivos ausentes são definitivos."""
    assert is_recoverable(exc) is False
    assert is_definitive(exc) is True
    assert classify_failure(exc) == FailureCategory.DEFINITIVE


# =====================================================================
# 7. Testes de Encadeamento de Causa (__cause__) e Fallbacks
# =====================================================================
def test_generic_wrapper_with_recoverable_cause():
    """Exceção genérica envolvendo falha de rede deve ser recuperável."""
    wrapper = RuntimeError("Falha genérica na orquestração")
    wrapper.__cause__ = TimeoutError("timeout na API externa")

    assert is_recoverable(wrapper) is True
    assert classify_failure(wrapper) == FailureCategory.RECOVERABLE


def test_generic_wrapper_with_definitive_cause():
    """Exceção genérica envolvendo erro de validação deve ser definitiva."""
    wrapper = RuntimeError("Falha na orquestração")
    wrapper.__cause__ = ValueError("campo obrigatório ausente")

    assert is_recoverable(wrapper) is False
    assert is_definitive(wrapper) is True
    assert classify_failure(wrapper) == FailureCategory.DEFINITIVE


def test_unknown_exception_fallback():
    """Exceções desconhecidas devem ter fallback conservador (não retentar)."""
    unknown = RuntimeError("Erro desconhecido e sem causa definida")

    assert is_recoverable(unknown) is False
    assert is_definitive(unknown) is True
    assert classify_failure(unknown) == FailureCategory.DEFINITIVE


def test_non_exception_input_handling():
    """Passagem de valores não-exceção deve retornar seguro (False)."""
    assert is_recoverable(None) is False  # type: ignore
    assert is_recoverable("erro em string") is False  # type: ignore
    assert is_definitive("erro em string") is True  # type: ignore
