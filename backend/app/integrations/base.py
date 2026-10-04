from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload


class IntegrationError(Exception):
    """Exceção base para erros relacionados ao módulo de integrações."""


class ProviderNotFoundError(IntegrationError):
    """Lançada quando um provedor solicitado não foi encontrado ou registrado."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Provedor de integração '{provider_name}' não encontrado.")


class ProviderExecutionError(IntegrationError):
    """Lançada quando ocorre um erro interno não recuperável na execução do provedor."""

    def __init__(self, provider_name: str, message: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Falha na execução do provedor '{provider_name}': {message}")


class IntegrationProvider(ABC):
    """Contrato base para provedores de integração externa."""

    name: str

    @abstractmethod
    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        """Envia o resultado estruturado da reunião para a plataforma externa.

        Deve isolar falhas de comunicação e garantir que o retorno seja sempre
        uma instância de IntegrationResult, sem propagar exceções de rede que
        possam impactar o fluxo principal da aplicação.
        """
        pass
