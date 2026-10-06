from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.exceptions import is_recoverable
from app.core.failure_recorder import FailureRecord, FailureRecorder
from app.core.retry import RetryPolicy
from app.models.meeting_status import MeetingStatus

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JobRunner:
    """Executor central de operações para workers e jobs assíncronos.

    Implementa o fluxo determinístico:
    Job -> Operação:
      - sucesso -> continua
      - erro recuperável -> retry (com backoff exponencial; estado permanece consistente)
      - erro definitivo ou esgotamento -> registra falha sanitizada, marca FAILED e encerra.

    Evita duplicação da lógica de retry entre serviços através do uso centralizado
    de `app.core.retry.RetryPolicy` e garante previsibilidade de comportamento
    entre diferentes provedores (STT, LLM, diarização, etc.).
    """

    def __init__(
        self,
        retry_policy: RetryPolicy | None = None,
        meeting_repository: Any | None = None,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy.from_settings()
        self.meeting_repository = meeting_repository
        self.failures: list[FailureRecord] = []
        self.last_failure: FailureRecord | None = None

    def execute_operation(
        self,
        operation: Callable[..., T],
        *args: Any,
        meeting: Any | None = None,
        stage: str = "unknown",
        on_success: Callable[[T], None] | None = None,
        on_failure: Callable[[BaseException], None] | None = None,
        **kwargs: Any,
    ) -> T:
        """Executa uma operação síncrona dentro do job assíncrono."""
        attempts = 0

        def _counted_operation(*op_args: Any, **op_kwargs: Any) -> T:
            nonlocal attempts
            attempts += 1
            return operation(*op_args, **op_kwargs)

        try:
            result = self.retry_policy.execute(_counted_operation, *args, **kwargs)
            if on_success is not None:
                on_success(result)
            return result
        except Exception as exc:
            self._handle_operation_failure(
                stage=stage,
                exc=exc,
                attempts=attempts,
                meeting=meeting,
                on_failure=on_failure,
            )
            raise

    async def execute_async_operation(
        self,
        coro_func: Callable[..., Awaitable[T]],
        *args: Any,
        meeting: Any | None = None,
        stage: str = "unknown",
        on_success: Callable[[T], None] | None = None,
        on_failure: Callable[[BaseException], None] | None = None,
        **kwargs: Any,
    ) -> T:
        """Executa uma operação assíncrona dentro do job assíncrono."""
        attempts = 0

        async def _counted_async_operation(*op_args: Any, **op_kwargs: Any) -> T:
            nonlocal attempts
            attempts += 1
            return await coro_func(*op_args, **op_kwargs)

        try:
            result = await self.retry_policy.execute_async(
                _counted_async_operation, *args, **kwargs
            )
            if on_success is not None:
                on_success(result)
            return result
        except Exception as exc:
            self._handle_operation_failure(
                stage=stage,
                exc=exc,
                attempts=attempts,
                meeting=meeting,
                on_failure=on_failure,
            )
            raise

    def _handle_operation_failure(
        self,
        stage: str,
        exc: BaseException,
        attempts: int,
        meeting: Any | None,
        on_failure: Callable[[BaseException], None] | None,
    ) -> FailureRecord:
        """Registra a falha com contexto seguro e transiciona a reunião para FAILED."""
        record = FailureRecorder.record_failure(
            stage=stage,
            error=exc,
            attempts=max(1, attempts),
        )
        self.last_failure = record
        self.failures.append(record)

        if on_failure is not None:
            try:
                on_failure(exc)
            except Exception as cb_exc:
                logger.error("Erro ao executar callback on_failure: %s", cb_exc)

        if meeting is not None:
            if hasattr(meeting, "status"):
                meeting.status = MeetingStatus.FAILED

            if self.meeting_repository is not None:
                db = getattr(self.meeting_repository, "db", None)
                if db is not None and hasattr(db, "rollback"):
                    try:
                        db.rollback()
                        if hasattr(meeting, "transcript"):
                            meeting.transcript = None
                        if hasattr(meeting, "summary"):
                            meeting.summary = None
                        if hasattr(meeting, "tasks") and meeting.tasks:
                            meeting.tasks.clear()
                    except Exception:
                        pass
                try:
                    self.meeting_repository.update_status(meeting, MeetingStatus.FAILED)
                    logger.info(
                        "Status da reunião %s atualizado para FAILED na etapa '%s'.",
                        getattr(meeting, "id", meeting),
                        stage,
                    )
                except Exception as repo_exc:
                    logger.error(
                        "Falha ao persistir status FAILED no repositório de reuniões: %s",
                        repo_exc,
                    )

        return record

