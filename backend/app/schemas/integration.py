from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskIntegrationPayload(BaseModel):
    """Payload de uma tarefa para integrações externas."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Identificador da tarefa no banco, se houver.")
    description: str = Field(..., min_length=1, description="Descrição da ação a ser executada.")
    responsible: str | None = Field(default=None, description="Pessoa responsável pela tarefa.")
    deadline: date | str | None = Field(
        default=None,
        description="Prazo da tarefa (formato ISO date ou representação textual).",
    )


class MeetingIntegrationPayload(BaseModel):
    """Payload de dados consolidados da reunião enviado para integrações."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: int = Field(..., gt=0, description="Identificador único da reunião.")
    title: str = Field(..., min_length=1, description="Título da reunião.")
    summary: str = Field(..., min_length=1, description="Resumo executivo da reunião.")
    objective: str | None = Field(default=None, description="Objetivo principal identificado.")
    key_points: list[str] = Field(default_factory=list, description="Lista dos tópicos e pontos principais.")
    decisions: list[str] = Field(default_factory=list, description="Lista de decisões tomadas na reunião.")
    tasks: list[TaskIntegrationPayload] = Field(default_factory=list, description="Lista de tarefas extraídas.")
    created_at: datetime | None = Field(default=None, description="Data/hora de criação da reunião.")


class IntegrationResult(BaseModel):
    """Resultado da execução de um envio para um provider de integração."""

    model_config = ConfigDict(from_attributes=True)

    provider: str = Field(..., min_length=1, description="Nome identificador do provider (ex: console, discord).")
    success: bool = Field(..., description="Indica se o envio foi bem-sucedido.")
    error: str | None = Field(default=None, description="Mensagem de erro segura em caso de falha.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadados adicionais da execução (ex: IDs externos, timestamps, status HTTP).",
    )
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp UTC de quando a integração foi disparada.",
    )
