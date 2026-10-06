from __future__ import annotations

import asyncio
import logging
from typing import Any

from google import genai
from google.genai import errors

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


class GeminiProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        retry_policy: RetryPolicy | None = None,
    ):
        if not api_key or not str(api_key).strip():
            raise LLMConfigurationError("Chave de API do Gemini ausente ou inválida.")
        if not model or not str(model).strip():
            raise LLMConfigurationError("Modelo do Gemini não informado.")

        self._client = genai.Client(api_key=api_key.strip())
        self._model = model.strip()
        self.retry_policy = retry_policy or RetryPolicy.from_settings()

    def generate(self, prompt: str) -> str:
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        attempts = 0

        def _counted_attempt(*args: Any, **kwargs: Any) -> str:
            nonlocal attempts
            attempts += 1
            return self._generate_attempt(*args, **kwargs)

        try:
            result = self.retry_policy.execute(_counted_attempt, prompt)
        except Exception:
            logger.error(
                "Geração LLM (Gemini) falhou após %d tentativa(s).",
                attempts,
            )
            raise

        logger.info(
            "Geração LLM (Gemini) concluída em %d tentativa(s).",
            attempts,
        )
        return result

    def _generate_attempt(self, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
        except errors.ClientError as exc:
            code = getattr(exc, "code", None)
            err_msg = str(getattr(exc, "message", None) or exc).lower()

            if code in (401, 403) or any(
                token in err_msg for token in ("unauthenticated", "permission_denied")
            ):
                raise LLMAuthenticationError(str(exc)) from exc

            if code == 429 or any(
                token in err_msg for token in ("rate limit", "resource_exhausted", "quota")
            ):
                raise LLMRateLimitError(str(exc)) from exc

            if code in (408, 504) or any(
                token in err_msg for token in ("timeout", "timed out", "deadline_exceeded")
            ):
                raise LLMTimeoutError(f"Timeout na chamada ao Gemini: {exc}") from exc

            # Erros definitivos de entrada/requisição (HTTP 400, 422, etc.)
            raise LLMProviderError(str(exc), is_retryable=False) from exc

        except errors.ServerError as exc:
            code = getattr(exc, "code", None)
            err_msg = str(getattr(exc, "message", None) or exc).lower()

            if code == 504 or any(
                token in err_msg for token in ("timeout", "timed out", "deadline_exceeded")
            ):
                raise LLMTimeoutError(f"Timeout no servidor do Gemini: {exc}") from exc

            # Falhas temporárias e indisponibilidade do servidor (500, 502, 503)
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
                ),
            ):
                raise

            if isinstance(exc, LLMProviderError):
                raise

            err_msg = str(exc).lower()

            if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or any(
                token in err_msg for token in ("timeout", "timed out", "deadline_exceeded")
            ):
                raise LLMTimeoutError(f"Timeout na chamada ao Gemini: {exc}") from exc

            if any(
                token in err_msg for token in ("rate limit", "resource_exhausted", "quota", "429")
            ):
                raise LLMRateLimitError(str(exc)) from exc

            if isinstance(exc, ConnectionError) or any(
                token in err_msg for token in ("connection", "unavailable", "502", "503")
            ):
                raise LLMProviderError(
                    f"Indisponibilidade temporária do provedor Gemini: {exc}",
                    is_retryable=True,
                ) from exc

            if isinstance(exc, (ValueError, TypeError)):
                raise LLMProviderError(str(exc), is_retryable=False) from exc

            raise LLMProviderError(str(exc)) from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMEmptyResponseError("O provider retornou uma resposta vazia.")

        return text

