from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.integration_configuration import IntegrationConfiguration


class ProviderConfigurationError(ValueError):
    """A configuração necessária para um provider não está disponível."""


class ProviderConfigurationResolver:
    """Obtém a configuração de cada provider a partir da reunião."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def resolve(
        self,
        provider: str,
        *,
        meeting_id: int | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retorna os argumentos de inicialização do provider solicitado."""
        provider_name = provider.strip().lower()
        configuration = self._meeting_configuration(provider_name, meeting_id)
        configuration.update(overrides or {})
        return configuration

    def _meeting_configuration(
        self,
        provider: str,
        meeting_id: int | None,
    ) -> dict[str, Any]:
        if self._db is None or meeting_id is None:
            return {}

        statement = select(IntegrationConfiguration).where(
            IntegrationConfiguration.meeting_id == meeting_id,
            func.lower(IntegrationConfiguration.platform) == provider,
        )
        configuration = self._db.scalars(statement).first()
        if configuration is None:
            return {}
        if not configuration.enabled:
            raise ProviderConfigurationError("Provider desativado para esta reunião")
        if configuration.configuration is None:
            return {}
        if not isinstance(configuration.configuration, dict):
            raise ProviderConfigurationError("Configuração do provider inválida")
        return dict(configuration.configuration)
