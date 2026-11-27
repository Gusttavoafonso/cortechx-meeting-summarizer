from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.secret_crypto import SecretDecryptionError, decrypt_config_secrets
from app.models.integration_configuration import IntegrationConfiguration
from app.models.meeting import Meeting
from app.models.user_integration import UserIntegration


class ProviderConfigurationError(ValueError):
    """A configuração necessária para um provider não está disponível."""


class ProviderDisabledError(ProviderConfigurationError):
    """O provider está desativado para a reunião especificada."""


class ProviderConfigurationResolver:
    """Obtém a configuração de cada provider (reunião -> usuário -> .env)."""

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
        meeting_cfg = self._meeting_configuration_record(provider_name, meeting_id)
        if meeting_cfg is not None and not meeting_cfg.enabled:
            raise ProviderDisabledError("Provider desativado para esta reunião.")

        user_cfg = self._user_configuration(
            provider_name,
            meeting_id,
            allow_disabled=meeting_cfg is None,
        )

        resolved: dict[str, Any] = {}
        resolved.update(user_cfg)
        if meeting_cfg is not None and meeting_cfg.configuration is not None:
            if not isinstance(meeting_cfg.configuration, dict):
                raise ProviderConfigurationError("Configuração do provider inválida.")
            resolved.update(meeting_cfg.configuration)
        resolved.update(overrides or {})
        return resolved

    def _meeting_configuration_record(
        self,
        provider: str,
        meeting_id: int | None,
    ) -> IntegrationConfiguration | None:
        if self._db is None or meeting_id is None:
            return None

        statement = select(IntegrationConfiguration).where(
            IntegrationConfiguration.meeting_id == meeting_id,
            func.lower(IntegrationConfiguration.platform) == provider,
        )
        return self._db.scalars(statement).first()

    def _user_configuration(
        self,
        provider: str,
        meeting_id: int | None,
        *,
        allow_disabled: bool,
    ) -> dict[str, Any]:
        if self._db is None or meeting_id is None:
            return {}

        user_id = self._db.scalar(
            select(Meeting.user_id).where(Meeting.id == meeting_id)
        )
        if user_id is None:
            return {}

        statement = select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            func.lower(UserIntegration.provider) == provider,
        )
        user_integration = self._db.scalars(statement).first()
        if user_integration is None:
            return {}
        if not user_integration.enabled:
            if allow_disabled:
                raise ProviderDisabledError("Provider desativado pelo usuário.")
            return {}
        if user_integration.config is None:
            return {}
        if not isinstance(user_integration.config, dict):
            raise ProviderConfigurationError(
                "Configuração do provider do usuário inválida."
            )
        try:
            decrypted = decrypt_config_secrets(
                user_integration.config,
                user_id=user_id,
                provider=provider,
            )
        except SecretDecryptionError as exc:
            raise ProviderConfigurationError(
                "Falha ao descriptografar as credenciais da integração."
            ) from exc
        return {
            key: value
            for key, value in decrypted.items()
            if value is not None and value != ""
        }
