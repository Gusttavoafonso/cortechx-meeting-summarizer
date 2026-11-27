from __future__ import annotations

import asyncio
import logging

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.retry import RetryPolicy
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Provider para APIs compatíveis com OpenAI Chat Completions (OpenAI, Groq)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider_name: str = "openai",
        base_url: str | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not api_key or not str(api_key).strip():
            raise LLMConfigurationError(
                f"Chave de API ({provider_name}) ausente ou inválida."
            )
        if not model or not str(model).strip():
            raise LLMConfigurationError(f"Modelo ({provider_name}) não informado.")

        self._provider_name = provider_name
        self._model = model.strip()
        self._client = OpenAI(
            api_key=api_key.strip(),
            **({"base_url": base_url} if base_url else {}),
        )
        self.retry_policy = retry_policy or RetryPolicy.from_settings()

    def generate(self, prompt: str) -> str:
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        attempts = 0

        def _counted_attempt(*args: object, **kwargs: object) -> str:
            nonlocal attempts
            attempts += 1
            return self._generate_attempt(prompt)

        try:
            result = self.retry_policy.execute(_counted_attempt, prompt)
        except Exception:
            logger.error(
                "Geração LLM (%s) falhou após %d tentativa(s).",
                self._provider_name,
                attempts,
            )
            raise

        logger.info(
            "Geração LLM (%s) concluída em %d tentativa(s).",
            self._provider_name,
            attempts,
        )
        return result

    def _generate_attempt(self, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise LLMAuthenticationError(str(exc)) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except (APITimeoutError, TimeoutError, asyncio.TimeoutError) as exc:
            raise LLMTimeoutError(
                f"Timeout na chamada ao {self._provider_name}: {exc}"
            ) from exc
        except BadRequestError as exc:
            raise LLMProviderError(str(exc), is_retryable=False) from exc
        except APIConnectionError as exc:
            raise LLMProviderError(
                f"Falha de conexão com {self._provider_name}: {exc}",
                is_retryable=True,
            ) from exc
        except APIStatusError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code in (401, 403):
                raise LLMAuthenticationError(str(exc)) from exc
            if status_code == 429:
                raise LLMRateLimitError(str(exc)) from exc
            if status_code in (408, 504):
                raise LLMTimeoutError(str(exc)) from exc
            is_retryable = status_code is not None and status_code >= 500
            raise LLMProviderError(str(exc), is_retryable=is_retryable) from exc
        except APIError as exc:
            raise LLMProviderError(str(exc), is_retryable=True) from exc
        except Exception as exc:
            if isinstance(
                exc,
                (
                    LLMAuthenticationError,
                    LLMConfigurationError,
                    LLMEmptyResponseError,
                    LLMTimeoutError,
                    LLMRateLimitError,
                    LLMProviderError,
                ),
            ):
                raise
            raise LLMProviderError(str(exc)) from exc

        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        text = getattr(message, "content", None)
        if not text or not str(text).strip():
            raise LLMEmptyResponseError("O provider retornou uma resposta vazia.")

        return str(text)
