from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None


class TaskItem(BaseModel):
    """Tarefa como devolvida pelo pipeline de sumarização."""

    description: str = Field(..., min_length=1)
    responsible: str | None = Field(default=None, max_length=255)
    deadline: date | None = Field(
        default=None,
        description="Prazo já resolvido para uma data (ISO 8601). Nulo se ausente.",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("A descrição da tarefa não pode ser vazia.")
        return clean

    @field_validator("responsible")
    @classmethod
    def normalize_responsible(cls, v: str | None) -> str | None:
        return _strip_or_none(v)


class SummaryResult(BaseModel):
    """Contrato do resultado estruturado produzido pelo pipeline."""

    objective: str | None = None
    summary: str = Field(..., min_length=1)
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, v: str | None) -> str | None:
        return _strip_or_none(v)

    @field_validator("key_points", "decisions")
    @classmethod
    def drop_blank_items(cls, v: list[str]) -> list[str]:
        return [item.strip() for item in v if item and item.strip()]


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    description: str
    responsible: str | None = None
    deadline: date | None = None
    created_at: datetime


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    objective: str | None = None
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    tasks: list[TaskResponse] = Field(default_factory=list)
    structured_result: dict[str, Any] | None = None
    generation_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
