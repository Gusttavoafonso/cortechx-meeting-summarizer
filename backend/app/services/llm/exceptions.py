"""Exceções do serviço de LLM baseadas no domínio central da aplicação."""

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

__all__ = [
    "LLMError",
    "LLMConfigurationError",
    "LLMAuthenticationError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMEmptyResponseError",
    "LLMProviderError",
]
