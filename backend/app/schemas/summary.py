"""Schemas da saída de sumarização gerada pela LLM."""

from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    """Estrutura validada da resposta de sumarização de uma reunião."""

    objective: str = Field(
        description="Objetivo da reunião identificado na transcrição."
    )
    summary: str = Field(
        description="Resumo geral fiel ao conteúdo da transcrição."
    )
    main_points: list[str] = Field(
        description="Principais assuntos discutidos na reunião."
    )
    decisions: list[str] = Field(
        description="Decisões relevantes explicitamente tomadas na reunião."
    )
