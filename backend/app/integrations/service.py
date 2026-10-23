from __future__ import annotations

import logging
from typing import Any

from app.integrations.base import ProviderNotFoundError
from app.integrations.configuration import (
    ProviderConfigurationError,
    ProviderConfigurationResolver,
    ProviderDisabledError,
)
from app.integrations.payload import (
    MeetingResultUnavailableError,
    meeting_to_integration_payload,
)
from app.integrations.registry import ProviderRegistry, default_registry
from app.models.meeting import Meeting
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload

logger = logging.getLogger(__name__)


# Define uma classe generalista para qualquer provider registrado.


class IntegrationService:
    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        configuration_resolver: ProviderConfigurationResolver | None = None,
    ) -> None:
        self._registry = registry or default_registry
        self._configuration_resolver = (
            configuration_resolver or ProviderConfigurationResolver()
        )

    # o send é o método principal que executa a integração com o provider especificado,
    # lidando com erros inesperados e retornando um resultado seguro.
    def send(
        self,
        provider: str,
        meeting_result: MeetingIntegrationPayload,
        # Permite argumentos específicos de cada provider.
        **provider_config: Any,
    ) -> IntegrationResult:
        """Executa um provider e converte erros inesperados em retorno seguro.

        A integração não grava nem altera os dados da reunião; uma falha fica
        restrita ao resultado retornado por este método.
        """
        provider_name = provider.strip().lower()
        safe_provider = provider_name or "unknown"

        try:
            resolved_config = self._configuration_resolver.resolve(
                provider_name,
                meeting_id=meeting_result.meeting_id,
                overrides=provider_config,
            )
            integration_provider = self._registry.create(
                provider_name,
                **resolved_config,
            )
        except ProviderDisabledError as exc:
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error=str(exc) or "Provider desativado para esta reunião.",
            )
        except ProviderConfigurationError as exc:
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error=(
                    str(exc)
                    if str(exc)
                    else (
                        "A configuração do provider de integração está ausente "
                        "ou inválida."
                    )
                ),
            )
        except ProviderNotFoundError:
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error="Provider de integração não encontrado.",
            )
        except Exception:
            logger.exception(
                "Falha ao inicializar o provider de integração %s", provider_name
            )
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error="Não foi possível inicializar o provider de integração.",
            )

        try:
            result = integration_provider.send(meeting_result)
            if not result.provider or result.provider == "unknown":
                result.provider = safe_provider
            elif result.provider != provider_name and provider_name:
                result.provider = provider_name
            return result
        except Exception:
            logger.exception(
                "Falha ao executar o provider de integração %s", provider_name
            )
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error="Não foi possível executar a integração.",
            )

    def send_persisted_meeting(
        self,
        provider: str,
        meeting: Meeting,
        **provider_config: Any,
    ) -> IntegrationResult:
        """Converte o resultado persistido e o envia ao provider solicitado."""
        safe_provider = provider.strip().lower() or "unknown"
        try:
            payload = meeting_to_integration_payload(meeting)
        except MeetingResultUnavailableError as exc:
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.exception(
                "Falha ao converter reunião para integração: %s",
                getattr(meeting, "id", None),
            )
            return IntegrationResult(
                provider=safe_provider,
                success=False,
                error=str(exc) or "Não foi possível preparar os dados da reunião.",
            )
        return self.send(provider, payload, **provider_config)
