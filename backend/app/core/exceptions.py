"""Estrutura padronizada de exceções de domínio da aplicação CortechX.

Define a hierarquia completa de exceções de domínio derivadas de `ApplicationError`,
diferenciando falhas transitórias (passíveis de retry) de falhas definitivas.
"""

from __future__ import annotations

from typing import Any


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

    def __str__(self) -> str:
        return self.message or self.__class__.__name__


# =====================================================================
# 1. Transcription (Speech-to-Text)
# =====================================================================
class TranscriptionError(ApplicationError):
    """Erro base para operações do pipeline de transcrição (STT)."""

    is_retryable: bool = False


class TranscriptionAudioNotFoundError(TranscriptionError, FileNotFoundError):
    """Arquivo de áudio não foi encontrado para transcrição."""

    is_retryable: bool = False


class TranscriptionAudioCorruptedError(TranscriptionError):
    """Arquivo de áudio corrompido, formato inválido ou codec não suportado."""

    is_retryable: bool = False


class TranscriptionEmptyResponseError(TranscriptionError):
    """O serviço de transcrição retornou resposta vazia (áudio mudo ou inaudível)."""

    is_retryable: bool = False


class TranscriptionTimeoutError(TranscriptionError):
    """A requisição ao serviço de transcrição excedeu o tempo limite (transitório)."""

    is_retryable: bool = True


class TranscriptionRateLimitError(TranscriptionError):
    """Limite de requisições excedido no serviço de transcrição (transitório)."""

    is_retryable: bool = True


class TranscriptionProviderError(TranscriptionError):
    """Falha de comunicação ou erro de infraestrutura do provedor de transcrição."""

    is_retryable: bool = True


# =====================================================================
# 2. Diarization (Pyannote)
# =====================================================================
class DiarizationError(ApplicationError):
    """Erro base para operações do serviço de diarização de locutores."""

    is_retryable: bool = False


class DiarizationConfigurationError(DiarizationError):
    """Configuração necessária para diarização ausente ou inválida (ex: HF token)."""

    is_retryable: bool = False


class DiarizationAudioNotFoundError(DiarizationError, FileNotFoundError):
    """Arquivo de áudio não encontrado para execução da diarização."""

    is_retryable: bool = False


class DiarizationEmptyResponseError(DiarizationError):
    """O provedor de diarização não retornou nenhum segmento de locução."""

    is_retryable: bool = False


class DiarizationAssociationError(DiarizationError):
    """Falha ao associar locutores identificados aos segmentos de transcrição."""

    is_retryable: bool = False


class DiarizationProviderError(DiarizationError):
    """Falha durante a execução interna do pipeline ou modelo de diarização."""

    is_retryable: bool = False


# =====================================================================
# 3. LLM (Large Language Models)
# =====================================================================
class LLMError(ApplicationError):
    """Erro base para qualquer falha do serviço de LLM."""

    is_retryable: bool = False


class LLMConfigurationError(LLMError):
    """Configuração obrigatória ausente ou inválida (API Key, provider, model)."""

    is_retryable: bool = False


class LLMAuthenticationError(LLMError):
    """Falha de autenticação ou credenciais inválidas com o provedor de LLM."""

    is_retryable: bool = False


class LLMTimeoutError(LLMError):
    """A chamada ao provedor de LLM excedeu o tempo limite (transitório)."""

    is_retryable: bool = True


class LLMProviderError(LLMError):
    """Erro retornado pela API do provedor (falha interna, rede ou 5xx)."""

    is_retryable: bool = True


class LLMRateLimitError(LLMProviderError):
    """Limite de taxa (rate limit/quota) excedido no provedor de LLM (transitório)."""

    is_retryable: bool = True


class LLMEmptyResponseError(LLMError):
    """O provedor de LLM retornou uma resposta vazia ou sem conteúdo utilizável."""

    is_retryable: bool = False


# =====================================================================
# 4. Persistence (Database & Storage)
# =====================================================================
class PersistenceError(ApplicationError):
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


class ChunkingError(ProcessingError):
    """Falha durante o fatiamento determinístico da transcrição em chunks."""

    is_retryable: bool = False


class SummarizationError(ProcessingError, RuntimeError):
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


class TaskExtractionInvalidResponseError(TaskExtractionError):
    """Resposta do LLM inválida ou incompatível com o schema de tarefas."""

    is_retryable: bool = False


class TaskExtractionLLMFailureError(TaskExtractionError):
    """Falha na chamada ao serviço de LLM durante extração de tarefas."""

    is_retryable: bool = True
