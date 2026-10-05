from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings


class ProviderConfigurationError(ValueError):
    """A configuração necessária para um provider não está disponível."""


class ProviderConfigurationResolver:
    """Obtém a configuração de cada provider a partir das configurações da app."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def resolve(self, provider: str) -> dict[str, Any]:
        """Retorna os argumentos de inicialização do provider solicitado."""
        provider_name = provider.strip().lower()

        if provider_name == "discord":
            webhook_url = self._settings.discord_webhook_url
            if webhook_url is None:
                raise ProviderConfigurationError("DISCORD_WEBHOOK_URL")
            return {"webhook_url": str(webhook_url)}

        if provider_name == "notion":
            token = self._settings.notion_token
            database_id = self._settings.notion_database_id
            if token is None or not database_id:
                raise ProviderConfigurationError(
                    "NOTION_TOKEN e NOTION_DATABASE_ID"
                )
            return {
                "token": token.get_secret_value(),
                "database_id": database_id,
            }

        return {}
