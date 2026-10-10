from __future__ import annotations

import logging
from typing import Any

from app.integrations.base import ProviderNotFoundError
from app.integrations.configuration import (
    ProviderConfigurationError,
    ProviderConfigurationResolver,
)
from app.integrations.payload import meeting_to_integration_payload
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
        except ProviderConfigurationError:
            return IntegrationResult(
                provider=provider_name or provider,
                success=False,
                error=(
                    "A configuração do provider de integração está ausente "
                    "ou inválida."
                ),
            )
        except ProviderNotFoundError:
            return IntegrationResult(
                provider=provider_name or provider,
                success=False,
                error="Provider de integração não encontrado.",
            )
        except Exception:
            logger.exception(
                "Falha ao inicializar o provider de integração %s", provider_name
            )
            return IntegrationResult(
                provider=provider_name or provider,
                success=False,
                error="Não foi possível inicializar o provider de integração.",
            )

        try:
            result = integration_provider.send(meeting_result)
            if result.provider != provider_name:
                result.provider = provider_name
            return result
        except Exception:
            logger.exception(
                "Falha ao executar o provider de integração %s", provider_name
            )
            return IntegrationResult(
                provider=provider_name,
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
        payload = meeting_to_integration_payload(meeting)
        return self.send(provider, payload, **provider_config)
