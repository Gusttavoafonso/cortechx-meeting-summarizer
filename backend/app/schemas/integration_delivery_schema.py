from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.integration_delivery import IntegrationDeliveryStatus


class IntegrationDeliveryResponse(BaseModel):
    """Resultado da entrega do resumo a um provider externo."""

    model_config = ConfigDict(from_attributes=True)

    provider: str = Field(description="Nome do provider (ex.: discord, notion).")
    status: IntegrationDeliveryStatus = Field(
        description=(
            "pending: ainda não tentada; running: em andamento; "
            "success: entregue; failed: última tentativa falhou."
        )
    )
    attempts: int = Field(description="Tentativas de entrega já realizadas.")
    error_message: str | None = Field(
        default=None, description="Mensagem segura do último erro, se houver."
    )
    external_id: str | None = Field(
        default=None, description="Identificador no sistema externo, se houver."
    )
    executed_at: datetime | None = Field(
        default=None, description="Início da última tentativa."
    )
    updated_at: datetime


class MeetingIntegrationsResponse(BaseModel):
    meeting_id: int
    integrations: list[IntegrationDeliveryResponse]


class IntegrationRetryRequest(BaseModel):
    providers: list[str] | None = Field(
        default=None,
        description=(
            "Providers a reenviar. Sem este campo, reenvia todos os habilitados "
            "que ainda não foram entregues."
        ),
    )


class IntegrationRetryResponse(BaseModel):
    meeting_id: int
    providers: list[str] = Field(description="Providers agendados para reenvio.")
