"""Estrutura padronizada de exceções de domínio e classificação de falhas da CortechX.

Define a hierarquia completa de exceções de domínio derivadas de `ApplicationError`,
diferenciando falhas recuperáveis (passíveis de retry automático)
de falhas definitivas (que devem abortar imediatamente sem novas tentativas).
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class FailureCategory(str, Enum):
    """Categorias de falha para decisões de retry e controle de fluxo do pipeline."""

    RECOVERABLE = "recoverable"
    DEFINITIVE = "definitive"


class ApplicationError(Exception):
    """Exceção base para todas as falhas de domínio da aplicação.

    Atributos:
        message: Descrição legível do erro.
        is_retryable: Indica se a falha é transitória (passível de retry automático)
                      ou definitiva (erro permanente, não deve sofrer retry).
        details: Dicionário opcional contendo metadados ou contexto adicional do erro.
    """

    is_retryable: bool = False

    def __init__(
        self,
        message: str = "",
        *,
        is_retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if is_retryable is not None:
            self.is_retryable = is_retryable
        self.details = details or {}

    @property
    def category(self) -> FailureCategory:
        """Retorna a categoria da falha (RECOVERABLE ou DEFINITIVE)."""
        return (
            FailureCategory.RECOVERABLE
            if self.is_retryable
            else FailureCategory.DEFINITIVE
        )

    def __str__(self) -> str:
        return self.message or self.__class__.__name__


class RecoverableError(ApplicationError):
    """Falha transitória que pode ser recuperada através de retry automático.

    Exemplos de causas:
    - Timeouts de requisições de rede ou inferência
    - Rate limit excedido (HTTP 429)
    - Erro temporário de conexão ou rede
    - Indisponibilidade temporária de provedores externos (HTTP 502, 503, 504)
    """

    is_retryable: bool = True


class DefinitiveError(ApplicationError):
    """Falha definitiva (estrutural/permanente) que NÃO deve sofrer retry.

    Exemplos de causas:
    - Formato ou codec de áudio corrompido/inválido
    - Arquivo ou recurso não encontrado (HTTP 404)
    - Credenciais ausentes ou inválidas (HTTP 401, 403)
    - Entrada inválida ou schema não conforme (HTTP 400, 422)
    """

    is_retryable: bool = False


# =====================================================================
# 1. Transcription (Speech-to-Text)
# =====================================================================
class TranscriptionError(ApplicationError):
    """Erro base para operações do pipeline de transcrição (STT)."""

    is_retryable: bool = False


class TranscriptionAudioNotFoundError(
    TranscriptionError, DefinitiveError, FileNotFoundError
):
    """Arquivo de áudio não foi encontrado para transcrição."""

    is_retryable: bool = False


class TranscriptionAudioCorruptedError(TranscriptionError, DefinitiveError):
    """Arquivo de áudio corrompido, formato inválido ou codec não suportado."""

    is_retryable: bool = False


class TranscriptionEmptyResponseError(TranscriptionError, DefinitiveError):
    """O serviço de transcrição retornou resposta vazia (áudio mudo ou inaudível)."""

    is_retryable: bool = False


class TranscriptionTimeoutError(TranscriptionError, RecoverableError):
    """A requisição ao serviço de transcrição excedeu o tempo limite (transitório)."""

    is_retryable: bool = True


class TranscriptionRateLimitError(TranscriptionError, RecoverableError):
    """Limite de requisições excedido no serviço de transcrição (transitório)."""

    is_retryable: bool = True


class TranscriptionProviderError(TranscriptionError, RecoverableError):
    """Falha de comunicação ou erro de infraestrutura do provedor de transcrição."""

    is_retryable: bool = True


# =====================================================================
# 2. Diarization (Pyannote)
# =====================================================================
class DiarizationError(ApplicationError):
    """Erro base para operações do serviço de diarização de locutores."""

    is_retryable: bool = False


class DiarizationConfigurationError(DiarizationError, DefinitiveError):
    """Configuração necessária para diarização ausente ou inválida (ex: HF token)."""

    is_retryable: bool = False


class DiarizationAudioNotFoundError(
    DiarizationError, DefinitiveError, FileNotFoundError
):
    """Arquivo de áudio não encontrado para execução da diarização."""

    is_retryable: bool = False


class DiarizationEmptyResponseError(DiarizationError, DefinitiveError):
    """O provedor de diarização não retornou nenhum segmento de locução."""

    is_retryable: bool = False


class DiarizationAssociationError(DiarizationError, DefinitiveError):
    """Falha ao associar locutores identificados aos segmentos de transcrição."""

    is_retryable: bool = False


class DiarizationProviderError(DiarizationError, DefinitiveError):
    """Falha durante a execução interna do pipeline ou modelo de diarização."""

    is_retryable: bool = False


# =====================================================================
# 3. LLM (Large Language Models)
# =====================================================================
class LLMError(ApplicationError):
    """Erro base para qualquer falha do serviço de LLM."""

    is_retryable: bool = False


class LLMConfigurationError(LLMError, DefinitiveError):
    """Configuração obrigatória ausente ou inválida (API Key, provider, model)."""

    is_retryable: bool = False


class LLMAuthenticationError(LLMError, DefinitiveError):
    """Falha de autenticação ou credenciais inválidas com o provedor de LLM."""

    is_retryable: bool = False


class LLMTimeoutError(LLMError, RecoverableError):
    """A chamada ao provedor de LLM excedeu o tempo limite (transitório)."""

    is_retryable: bool = True


class LLMProviderError(LLMError, RecoverableError):
    """Erro retornado pela API do provedor (falha interna, rede ou 5xx)."""

    is_retryable: bool = True


class LLMRateLimitError(LLMProviderError):
    """Limite de taxa (rate limit/quota) excedido no provedor de LLM (transitório)."""

    is_retryable: bool = True


class LLMEmptyResponseError(LLMError, DefinitiveError):
    """O provedor de LLM retornou uma resposta vazia ou sem conteúdo utilizável."""

    is_retryable: bool = False


# =====================================================================
# 4. Persistence (Database & Storage)
# =====================================================================
class PersistenceError(DefinitiveError):
    """Erro base para falhas de persistência e acesso a dados."""

    is_retryable: bool = False


class EntityNotFoundError(PersistenceError):
    """Entidade consultada não foi encontrada no banco de dados."""

    is_retryable: bool = False


class MeetingNotFoundError(EntityNotFoundError):
    """A reunião informada não existe."""

    is_retryable: bool = False


class TranscriptNotFoundError(EntityNotFoundError):
    """A reunião existe, mas ainda não possui transcrição disponível."""

    is_retryable: bool = False


class AudioNotFoundError(EntityNotFoundError):
    """Arquivo ou registro de áudio da reunião não encontrado."""

    is_retryable: bool = False


class SummaryNotFoundError(EntityNotFoundError):
    """Resumo da reunião ainda não gerado ou não encontrado."""

    is_retryable: bool = False


class EntityConflictError(PersistenceError):
    """Conflito de estado ou concorrência na entidade informada."""

    is_retryable: bool = False


class SummaryAlreadyProcessingError(EntityConflictError):
    """Já existe um processamento de resumo em andamento para a reunião informada."""

    is_retryable: bool = False


class DatabaseError(PersistenceError):
    """Falha de comunicação ou erro na transação do banco de dados relacional."""

    is_retryable: bool = False


class InvalidPersistenceDataError(PersistenceError):
    """Dados estruturalmente inválidos para persistência no banco de dados."""

    is_retryable: bool = False


# =====================================================================
# 5. Processing (Chunking, Summarization, Task Extraction)
# =====================================================================
class ProcessingError(ApplicationError):
    """Erro base para falhas nas etapas de processamento intermediário."""

    is_retryable: bool = False


class ChunkingError(ProcessingError, DefinitiveError):
    """Falha durante o fatiamento determinístico da transcrição em chunks."""

    is_retryable: bool = False


class SummarizationError(ProcessingError, DefinitiveError, RuntimeError):
    """Falha durante o processo de sumarização de reuniões."""

    is_retryable: bool = False


class SummarizationEmptyInputError(SummarizationError, ValueError):
    """Tentativa de sumarização com transcrição vazia ou ausente."""

    is_retryable: bool = False


class SummarizationChunkProcessingError(SummarizationError):
    """Falha ao processar um chunk específico com o serviço de LLM."""

    is_retryable: bool = False


class SummarizationConsolidationError(SummarizationError):
    """Falha ao consolidar os resumos parciais dos chunks."""

    is_retryable: bool = False


class SummarizationInvalidResponseError(SummarizationError, ValueError):
    """Resposta da sumarização retornou formato JSON inválido ou incompatível."""

    is_retryable: bool = False


class TaskExtractionError(ProcessingError):
    """Exceção base para erros durante o processo de extração de tarefas."""

    is_retryable: bool = False


class TaskExtractionInvalidResponseError(TaskExtractionError, DefinitiveError):
    """Resposta do LLM inválida ou incompatível com o schema de tarefas."""

    is_retryable: bool = False


class TaskExtractionLLMFailureError(TaskExtractionError, RecoverableError):
    """Falha na chamada ao serviço de LLM durante extração de tarefas."""

    is_retryable: bool = True


# =====================================================================
# 6. Constantes e Classificação de Falhas (Recoverable vs Definitive)
# =====================================================================
RECOVERABLE_HTTP_STATUS_CODES: frozenset[int] = frozenset({429, 502, 503, 504})
DEFINITIVE_HTTP_STATUS_CODES: frozenset[int] = frozenset(
    {400, 401, 403, 404, 405, 409, 410, 413, 415, 422}
)

RECOVERABLE_BUILTIN_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
)

DEFINITIVE_BUILTIN_EXCEPTIONS: tuple[type[BaseException], ...] = (
    FileNotFoundError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    PermissionError,
    NotImplementedError,
)

RECOVERABLE_STATUS_CODES_STR: frozenset[str] = frozenset(
    {"RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED"}
)

DEFINITIVE_STATUS_CODES_STR: frozenset[str] = frozenset(
    {
        "INVALID_ARGUMENT",
        "NOT_FOUND",
        "PERMISSION_DENIED",
        "UNAUTHENTICATED",
        "ALREADY_EXISTS",
        "FAILED_PRECONDITION",
    }
)


def _extract_status_code(error: BaseException) -> int | None:
    """Extrai código de status HTTP numérico de exceções de SDKs/APIs."""
    code = getattr(error, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(error, "response", None)
    if response is not None:
        resp_code = getattr(response, "status_code", None)
        if isinstance(resp_code, int):
            return resp_code
    direct_code = getattr(error, "code", None)
    if isinstance(direct_code, int):
        return direct_code
    return None


def _extract_code_str(error: BaseException) -> str | None:
    """Extrai representação textual de código de status (ex: gRPC/Google GenAI)."""
    code = getattr(error, "code", None)
    if isinstance(code, str):
        return code.upper()
    status = getattr(error, "status", None)
    if isinstance(status, str):
        return status.upper()
    return None


def is_recoverable(error: BaseException) -> bool:
    """Determina se uma exceção é uma falha recuperável (passível de retry).

    Critérios de Classificação:
    1. Se o erro for instância de DefinitiveError, retorna False imediatamente
       (garante que erros definitivos abortem sem novas tentativas).
    2. Se o erro for instância de RecoverableError, retorna True imediatamente.
    3. Se o erro for ApplicationError, avalia o atributo `is_retryable`.
    4. Se o erro possuir status code HTTP associado:
       - 429, 502, 503, 504 -> True (transitório)
       - 400, 401, 403, 404, 409, 422 etc. -> False (definitivo)
    5. Se o erro possuir código de status em string (ex: Google GenAI/gRPC):
       - RESOURCE_EXHAUSTED, UNAVAILABLE, DEADLINE_EXCEEDED -> True
       - INVALID_ARGUMENT, NOT_FOUND, PERMISSION_DENIED etc. -> False
    6. Se o erro for exceção nativa do Python:
       - TimeoutError, ConnectionError -> True
       - FileNotFoundError, ValueError, TypeError, KeyError etc. -> False
    7. Se o erro contiver uma causa encapsulada (__cause__):
       - Avalia recursivamente a causa raiz (se não classificado definitivo).
    8. Fallback conservador: retorna False para exceções desconhecidas.
    """
    if not isinstance(error, BaseException):
        return False

    # 1. Regra estrita: DefinitiveError NUNCA deve sofrer retry
    if isinstance(error, DefinitiveError):
        return False

    # 2. RecoverableError sempre permite retry
    if isinstance(error, RecoverableError):
        return True

    # 3. ApplicationError com atributo is_retryable explícito
    if isinstance(error, ApplicationError):
        return bool(error.is_retryable)

    # 4. Status code HTTP numérico
    status_code = _extract_status_code(error)
    if status_code is not None:
        if status_code in RECOVERABLE_HTTP_STATUS_CODES:
            return True
        if status_code in DEFINITIVE_HTTP_STATUS_CODES:
            return False

    # 5. Códigos em string (Google / gRPC)
    code_str = _extract_code_str(error)
    if code_str:
        if code_str in RECOVERABLE_STATUS_CODES_STR:
            return True
        if code_str in DEFINITIVE_STATUS_CODES_STR:
            return False

    # 6. Exceções embutidas do Python
    if isinstance(error, RECOVERABLE_BUILTIN_EXCEPTIONS):
        return True
    if isinstance(error, DEFINITIVE_BUILTIN_EXCEPTIONS):
        return False

    # 7. Causa encapsulada (__cause__)
    if error.__cause__ is not None and error.__cause__ is not error:
        return is_recoverable(error.__cause__)

    # 8. Fallback conservador
    return False


def is_definitive(error: BaseException) -> bool:
    """Determina se uma falha é definitiva (não deve sofrer novas tentativas)."""
    return not is_recoverable(error)


def classify_failure(error: BaseException) -> FailureCategory:
    """Classifica deterministamente a falha como RECOVERABLE ou DEFINITIVE."""
    return (
        FailureCategory.RECOVERABLE
        if is_recoverable(error)
        else FailureCategory.DEFINITIVE
    )
