"""Módulo de política de retry para operações elegíveis da CortechX.

Implementa mecanismo de retentativas determinístico e configurável, com suporte
a backoff exponencial, jitter opcional, aborto imediato em falhas definitivas e
prevenção estrita de loop infinito (Issue #26 - Etapa 3).
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.exceptions import is_recoverable

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _default_sleep(delay: float) -> None:
    """Função de sleep padrão síncrona (ignora delay durante execução do pytest)."""
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
        "ENABLE_RETRY_SLEEP_IN_TESTS"
    ):
        return
    time.sleep(delay)


async def _default_async_sleep(delay: float) -> None:
    """Função de sleep padrão assíncrona (ignora delay durante execução do pytest)."""
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
        "ENABLE_RETRY_SLEEP_IN_TESTS"
    ):
        return
    await asyncio.sleep(delay)


class RetryPolicy:
    """Política de retry determinística e configurável para operações elegíveis.

    Atributos:
        max_attempts: Número máximo de tentativas (>= 1).
        initial_delay: Tempo de espera inicial em segundos após a primeira falha.
        backoff_factor: Fator multiplicador para crescimento do atraso (>= 1.0).
        jitter: Se True, adiciona variação aleatória no delay para evitar
                thundering herd.
        retryable_predicate: Predicado customizado para definir se um erro pode
                             ser retentado. Por padrão, utiliza
                             `app.core.exceptions.is_recoverable`.
        on_retry: Callback opcional executado a cada tentativa falha recuperável:
                  `callback(exc, attempt, delay)`.
        sleep_func: Função de espera síncrona (padrão: `time.sleep`).
        async_sleep_func: Função de espera assíncrona (padrão: `asyncio.sleep`).
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 10.0,
        jitter: bool = False,
        retryable_predicate: Callable[[BaseException], bool] | None = None,
        on_retry: Callable[[BaseException, int, float], None] | None = None,
        sleep_func: Callable[[float], None] | None = None,
        async_sleep_func: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts deve ser maior ou igual a 1.")
        if initial_delay < 0:
            raise ValueError("initial_delay deve ser maior ou igual a 0.")
        if backoff_factor < 1.0:
            raise ValueError("backoff_factor deve ser maior ou igual a 1.0.")
        if max_delay < initial_delay:
            raise ValueError("max_delay não pode ser menor que initial_delay.")

        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_predicate = retryable_predicate
        self.on_retry = on_retry
        self.sleep_func = sleep_func or _default_sleep
        self.async_sleep_func = async_sleep_func or _default_async_sleep

    def calculate_delay(self, attempt: int) -> float:
        """Calcula o tempo de espera em segundos para uma determinada tentativa.

        Fórmula:
            delay = min(initial_delay * (backoff_factor ** (attempt - 1)), max_delay)
        """
        if attempt < 1:
            attempt = 1
        base_delay = self.initial_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(base_delay, self.max_delay)

        if self.jitter and delay > 0:
            delay += random.uniform(0, 0.5 * delay)

        return round(delay, 4)

    def is_retryable(self, error: BaseException) -> bool:
        """Avalia se a exceção informada é passível de retry."""
        if self.retryable_predicate is not None:
            return self.retryable_predicate(error)
        return is_recoverable(error)

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Executa uma função síncrona aplicando a política de retry.

        Garante:
        1. Aborto imediato sem espera se o erro for definitivo.
        2. Impedimento absoluto de loop infinito (máximo de `max_attempts`).
        3. Espera com cálculo de intervalo entre tentativas para erros recuperáveis.
        4. Re-lançamento da exceção original caso o limite de tentativas se esgote.
        """
        op_name = getattr(func, "__name__", str(func))
        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if not self.is_retryable(exc):
                    logger.warning(
                        "Operação '%s' falhou com erro definitivo (%s: %s). "
                        "Abortando tentativas imediatamente.",
                        op_name,
                        exc.__class__.__name__,
                        exc,
                    )
                    raise

                if attempt >= self.max_attempts:
                    logger.error(
                        "Operação '%s' esgotou o número máximo de tentativas (%d/%d). "
                        "Falha final (%s): %s",
                        op_name,
                        attempt,
                        self.max_attempts,
                        exc.__class__.__name__,
                        exc,
                    )
                    raise

                delay = self.calculate_delay(attempt)
                logger.warning(
                    "Operação '%s' falhou na tentativa %d/%d (%s: %s). "
                    "Aguardando %.2fs antes da tentativa %d...",
                    op_name,
                    attempt,
                    self.max_attempts,
                    exc.__class__.__name__,
                    exc,
                    delay,
                    attempt + 1,
                )
                if self.on_retry is not None:
                    self.on_retry(exc, attempt, delay)

                self.sleep_func(delay)

        raise RuntimeError(f"Execução de '{op_name}' finalizada sem resultado.")

    async def execute_async(
        self, coro_func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Executa uma corrotina assíncrona aplicando a política de retry."""
        op_name = getattr(coro_func, "__name__", str(coro_func))
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as exc:
                if not self.is_retryable(exc):
                    logger.warning(
                        "Operação assíncrona '%s' falhou com erro definitivo (%s: %s). "
                        "Abortando tentativas imediatamente.",
                        op_name,
                        exc.__class__.__name__,
                        exc,
                    )
                    raise

                if attempt >= self.max_attempts:
                    logger.error(
                        "Operação assíncrona '%s' esgotou as tentativas (%d/%d). "
                        "Falha final (%s): %s",
                        op_name,
                        attempt,
                        self.max_attempts,
                        exc.__class__.__name__,
                        exc,
                    )
                    raise

                delay = self.calculate_delay(attempt)
                logger.warning(
                    "Operação assíncrona '%s' falhou na tentativa %d/%d (%s: %s). "
                    "Aguardando %.2fs antes da tentativa %d...",
                    op_name,
                    attempt,
                    self.max_attempts,
                    exc.__class__.__name__,
                    exc,
                    delay,
                    attempt + 1,
                )
                if self.on_retry is not None:
                    self.on_retry(exc, attempt, delay)

                await self.async_sleep_func(delay)

        raise RuntimeError(
            f"Execução assíncrona de '{op_name}' finalizada sem resultado."
        )

    @classmethod
    def from_settings(cls, app_settings: Any | None = None) -> RetryPolicy:
        """Constrói uma RetryPolicy a partir das configurações da aplicação."""
        if app_settings is None:
            from app.core.config import settings

            app_settings = settings

        return cls(
            max_attempts=getattr(app_settings, "RETRY_MAX_ATTEMPTS", 3),
            initial_delay=getattr(app_settings, "RETRY_INITIAL_DELAY", 1.0),
            backoff_factor=getattr(app_settings, "RETRY_BACKOFF_FACTOR", 2.0),
            max_delay=getattr(app_settings, "RETRY_MAX_DELAY", 10.0),
            jitter=getattr(app_settings, "RETRY_JITTER", False),
        )


def retry(
    func: Callable[..., Any] | None = None,
    *,
    policy: RetryPolicy | None = None,
    max_attempts: int | None = None,
    initial_delay: float | None = None,
    backoff_factor: float | None = None,
    max_delay: float | None = None,
    jitter: bool | None = None,
    retryable_predicate: Callable[[BaseException], bool] | None = None,
    on_retry: Callable[[BaseException, int, float], None] | None = None,
) -> Any:
    """Decorador flexível para aplicação de retry em funções síncronas/assíncronas."""
    effective_policy: RetryPolicy
    if policy is not None:
        effective_policy = policy
    else:
        kwargs: dict[str, Any] = {}
        if max_attempts is not None:
            kwargs["max_attempts"] = max_attempts
        if initial_delay is not None:
            kwargs["initial_delay"] = initial_delay
        if backoff_factor is not None:
            kwargs["backoff_factor"] = backoff_factor
        if max_delay is not None:
            kwargs["max_delay"] = max_delay
        if jitter is not None:
            kwargs["jitter"] = jitter
        if retryable_predicate is not None:
            kwargs["retryable_predicate"] = retryable_predicate
        if on_retry is not None:
            kwargs["on_retry"] = on_retry

        if kwargs:
            base = RetryPolicy.from_settings()
            effective_policy = RetryPolicy(
                max_attempts=kwargs.get("max_attempts", base.max_attempts),
                initial_delay=kwargs.get("initial_delay", base.initial_delay),
                backoff_factor=kwargs.get("backoff_factor", base.backoff_factor),
                max_delay=kwargs.get("max_delay", base.max_delay),
                jitter=kwargs.get("jitter", base.jitter),
                retryable_predicate=kwargs.get(
                    "retryable_predicate", base.retryable_predicate
                ),
                on_retry=kwargs.get("on_retry", base.on_retry),
            )
        else:
            effective_policy = RetryPolicy.from_settings()

    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(target):

            @functools.wraps(target)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await effective_policy.execute_async(target, *args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(target)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return effective_policy.execute(target, *args, **kwargs)

            return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
