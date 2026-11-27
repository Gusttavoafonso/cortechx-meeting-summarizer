from __future__ import annotations

import asyncio
import logging

import httpx

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

_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseLLMProvider):
    """Provider para Anthropic Claude Messages API via httpx."""

    def __init__(
        self,
        api_key: str,
        model: str,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not api_key or not str(api_key).strip():
            raise LLMConfigurationError("Chave de API (anthropic) ausente ou inválida.")
        if not model or not str(model).strip():
            raise LLMConfigurationError("Modelo (anthropic) não informado.")

        self._api_key = api_key.strip()
        self._model = model.strip()
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
                "Geração LLM (anthropic) falhou após %d tentativa(s).",
                attempts,
            )
            raise

        logger.info(
            "Geração LLM (anthropic) concluída em %d tentativa(s).",
            attempts,
        )
        return result

    def _generate_attempt(self, prompt: str) -> str:
        try:
            response = httpx.post(
                _ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
        except (httpx.TimeoutException, TimeoutError, asyncio.TimeoutError) as exc:
            raise LLMTimeoutError(f"Timeout na chamada ao Anthropic: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Falha de conexão com Anthropic: {exc}",
                is_retryable=True,
            ) from exc

        if response.status_code in (401, 403):
            raise LLMAuthenticationError(
                f"Anthropic retornou HTTP {response.status_code}."
            )
        if response.status_code == 429:
            raise LLMRateLimitError("Limite de requisições atingido no Anthropic.")
        if response.status_code in (408, 504):
            raise LLMTimeoutError(f"Timeout HTTP {response.status_code} no Anthropic.")
        if response.status_code >= 500:
            raise LLMProviderError(
                f"Erro temporário Anthropic HTTP {response.status_code}.",
                is_retryable=True,
            )
        if response.status_code >= 400:
            raise LLMProviderError(
                f"Erro na requisição Anthropic HTTP {response.status_code}.",
                is_retryable=False,
            )

        data = response.json()
        blocks = data.get("content") or []
        parts = [
            str(block.get("text"))
            for block in blocks
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and block.get("text")
            )
        ]
        text = "".join(parts).strip()
        if not text:
            raise LLMEmptyResponseError("O provider retornou uma resposta vazia.")

        return text
