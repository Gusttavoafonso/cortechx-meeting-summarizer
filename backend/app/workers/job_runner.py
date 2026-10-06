from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.exceptions import is_recoverable
from app.core.retry import RetryPolicy
from app.models.meeting_status import MeetingStatus

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JobRunner:
    """Executor central de operações para workers e jobs assíncronos.

    Implementa o fluxo determinístico:
    Job -> Operação:
      - sucesso -> continua
      - erro recuperável -> retry (com backoff exponencial)
      - erro definitivo ou esgotamento -> marca status como FAILED e encerra.

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

    def execute_operation(
        self,
        operation: Callable[..., T],
        *args: Any,
        meeting: Any | None = None,
        on_success: Callable[[T], None] | None = None,
        on_failure: Callable[[BaseException], None] | None = None,
        **kwargs: Any,
    ) -> T:
        """Executa uma operação síncrona dentro do job assíncrono."""
        op_name = getattr(operation, "__name__", str(operation))
        try:
            result = self.retry_policy.execute(operation, *args, **kwargs)
            if on_success is not None:
                on_success(result)
            return result
        except Exception as exc:
            self._handle_operation_failure(
                op_name=op_name,
                exc=exc,
                meeting=meeting,
                on_failure=on_failure,
            )
            raise

    async def execute_async_operation(
        self,
        coro_func: Callable[..., Awaitable[T]],
        *args: Any,
        meeting: Any | None = None,
        on_success: Callable[[T], None] | None = None,
        on_failure: Callable[[BaseException], None] | None = None,
        **kwargs: Any,
    ) -> T:
        """Executa uma operação assíncrona dentro do job assíncrono."""
        op_name = getattr(coro_func, "__name__", str(coro_func))
        try:
            result = await self.retry_policy.execute_async(coro_func, *args, **kwargs)
            if on_success is not None:
                on_success(result)
            return result
        except Exception as exc:
            self._handle_operation_failure(
                op_name=op_name,
                exc=exc,
                meeting=meeting,
                on_failure=on_failure,
            )
            raise

    def _handle_operation_failure(
        self,
        op_name: str,
        exc: BaseException,
        meeting: Any | None,
        on_failure: Callable[[BaseException], None] | None,
    ) -> None:
        """Trata o erro definitivo ou esgotamento de tentativas marcando como FAILED."""
        recoverable = is_recoverable(exc)
        logger.error(
            "Job falhou na operação '%s' (erro %s, recuperável=%s): %s",
            op_name,
            exc.__class__.__name__,
            recoverable,
            exc,
        )

        if on_failure is not None:
            try:
                on_failure(exc)
            except Exception as cb_exc:
                logger.error("Erro ao executar callback on_failure: %s", cb_exc)

        if meeting is not None and self.meeting_repository is not None:
            try:
                self.meeting_repository.update_status(meeting, MeetingStatus.FAILED)
                logger.info(
                    "Status da reunião %s atualizado para FAILED após falha da operação.",
                    getattr(meeting, "id", meeting),
                )
            except Exception as repo_exc:
                logger.error(
                    "Falha ao persistir status FAILED no repositório de reuniões: %s",
                    repo_exc,
                )
