from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_LLM_MODEL, DEFAULT_LLM_PROVIDER, settings
from app.core.secret_crypto import SecretDecryptionError, decrypt_secret
from app.models.user_integration import UserIntegration
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import LLMConfigurationError
from app.services.llm.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class LLMService:
    """Serviço central utilizado pela aplicação para comunicação com LLMs."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def generate(self, prompt: str) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        return self.provider.generate(prompt)


def _build_provider(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> BaseLLMProvider:
    if provider is None and model is None and api_key is None:
        try:
            settings.validate_llm_configuration()
        except ValueError as exc:
            raise LLMConfigurationError(str(exc)) from exc

        if settings.llm_provider == "gemini":
            return GeminiProvider(
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
            )

        raise LLMConfigurationError(
            f"Provider não suportado: {settings.llm_provider}"
        )

    eff_provider = (
        (provider or settings.llm_provider or DEFAULT_LLM_PROVIDER).strip().lower()
    )
    eff_model = (model or settings.llm_model or DEFAULT_LLM_MODEL).strip()
    eff_key = (
        api_key
        if api_key is not None
        else (
            settings.llm_api_key.get_secret_value()
            if settings.llm_api_key is not None
            else ""
        )
    ).strip()

    if not eff_model:
        raise LLMConfigurationError("Modelo de LLM não informado.")
    if not eff_key:
        raise LLMConfigurationError("Chave de API de LLM não configurada.")

    if eff_provider == "gemini":
        return GeminiProvider(api_key=eff_key, model=eff_model)

    raise LLMConfigurationError(f"Provider não suportado: {eff_provider}")


def get_llm_service(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMService:
    return LLMService(_build_provider(provider=provider, model=model, api_key=api_key))


def resolve_user_llm_config(
    db: Session | None,
    user_id: int | None,
) -> dict[str, str] | None:
    """Resolve a configuração pessoal de LLM ativa do usuário, se existir."""
    if db is None or user_id is None:
        return None

    row = db.scalar(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.provider == "llm",
            UserIntegration.enabled.is_(True),
        )
    )
    if row is None or not isinstance(row.config, dict):
        return None

    raw_key = row.config.get("api_key")
    if not isinstance(raw_key, str) or not raw_key.strip():
        return None

    try:
        decrypted_key = decrypt_secret(
            raw_key,
            user_id=user_id,
            provider="llm",
            field="api_key",
        ).strip()
    except SecretDecryptionError:
        logger.warning(
            "Falha ao descriptografar chave LLM pessoal do usuário %s.",
            user_id,
        )
        return None

    if not decrypted_key:
        return None

    raw_provider = row.config.get("llm_provider")
    raw_model = row.config.get("llm_model")
    provider_name = (
        str(raw_provider).strip().lower()
        if isinstance(raw_provider, str) and raw_provider.strip()
        else DEFAULT_LLM_PROVIDER
    )
    model_name = (
        str(raw_model).strip()
        if isinstance(raw_model, str) and raw_model.strip()
        else (settings.llm_model or DEFAULT_LLM_MODEL)
    )
    return {
        "provider": provider_name,
        "model": model_name,
        "api_key": decrypted_key,
    }
