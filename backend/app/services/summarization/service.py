"""Serviço de orquestração da sumarização de reuniões."""

import json
import re

from pydantic import ValidationError

from app.core.exceptions import (
    LLMError,
    SummarizationChunkProcessingError,
    SummarizationConsolidationError,
    SummarizationEmptyInputError,
    SummarizationError,
    SummarizationInvalidResponseError,
)
from app.prompts.summarization import build_summarization_prompt
from app.schemas.chunk import ChunkingConfig
from app.schemas.summary import SummaryResult
from app.services.chunking import ChunkingService
from app.services.llm.service import LLMService

_NOT_FOUND = "Não identificado na transcrição."


class SummarizationService:
    """Coordena chunking, LLM, validação e consolidação."""

    def __init__(self, llm: LLMService, chunker: ChunkingService) -> None:
        self.llm = llm
        self.chunker = chunker

    def summarize(self, transcript: str) -> SummaryResult:
        if not transcript or not transcript.strip():
            raise SummarizationEmptyInputError("A transcrição não pode estar vazia")

        chunks = self.chunker.split(transcript)
        if not chunks:
            raise SummarizationError("Não foi possível criar chunks da transcrição")

        partials = [self._summarize_chunk(chunk.text) for chunk in chunks]
        if len(partials) == 1:
            return partials[0]
        return self._consolidate(partials)

    def _summarize_chunk(self, chunk: str) -> SummaryResult:
        try:
            raw_text = self.llm.generate(build_summarization_prompt(chunk))
            return self._parse_result(raw_text)
        except SummarizationInvalidResponseError:
            raise
        except LLMError as exc:
            raise SummarizationChunkProcessingError(
                "Falha ao processar um chunk com o serviço de LLM"
            ) from exc
        except Exception as exc:
            raise SummarizationChunkProcessingError(
                "Falha ao processar um chunk com o serviço de LLM"
            ) from exc

    def _consolidate(self, partials: list[SummaryResult]) -> SummaryResult:
        material = self._build_consolidation_material(partials)
        prompt = f"""Você é responsável pela consolidação final de uma reunião.

Use exclusivamente os resultados parciais abaixo. Não invente informações.
Remova duplicações evidentes e preserve informações relevantes presentes em
qualquer resultado. Não transforme sugestões em decisões.

Se nenhum resultado permitir identificar o objetivo, use exatamente:
"{_NOT_FOUND}".
Se não houver decisões explícitas, retorne decisions como [].

Retorne exclusivamente um JSON válido, sem texto antes ou depois, com os
campos: objective, summary, key_points e decisions.

Resultados parciais:
---
{material}
---
"""
        try:
            raw_text = self.llm.generate(prompt)
            return self._parse_result(raw_text)
        except SummarizationInvalidResponseError:
            raise
        except LLMError as exc:
            raise SummarizationConsolidationError(
                "Falha ao consolidar os resultados da reunião"
            ) from exc
        except Exception as exc:
            raise SummarizationConsolidationError(
                "Falha ao consolidar os resultados da reunião"
            ) from exc

    @staticmethod
    def _parse_result(raw_text: str) -> SummaryResult:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise SummarizationInvalidResponseError(
                "O LLM não retornou um JSON válido"
            ) from exc

        try:
            return SummaryResult.model_validate(data)
        except ValidationError as exc:
            raise SummarizationInvalidResponseError(
                f"Formato inválido do resumo retornado pelo LLM: {exc}"
            ) from exc
        except Exception as exc:
            raise SummarizationInvalidResponseError(
                f"Falha de validação do resumo: {exc}"
            ) from exc

    @staticmethod
    def _build_consolidation_material(partials: list[SummaryResult]) -> str:
        seen_points: set[str] = set()
        seen_decisions: set[str] = set()
        blocks: list[str] = []

        for index, partial in enumerate(partials, start=1):
            points = []
            for point in partial.key_points:
                key = point.strip().casefold()
                if key and key not in seen_points:
                    seen_points.add(key)
                    points.append(point)

            decisions = []
            for decision in partial.decisions:
                key = decision.strip().casefold()
                if key and key not in seen_decisions:
                    seen_decisions.add(key)
                    decisions.append(decision)

            blocks.append(
                f"Resumo parcial {index}:\n"
                f"Objetivo: {partial.objective}\n"
                f"Resumo: {partial.summary}\n"
                f"Principais pontos: {points}\n"
                f"Decisões: {decisions}"
            )

        return "\n\n".join(blocks)


def create_summarization_service(
    llm: LLMService,
    *,
    max_chars: int = 12000,
    overlap_chars: int = 500,
) -> SummarizationService:
    return SummarizationService(
        llm=llm,
        chunker=ChunkingService(
            default_config=ChunkingConfig(
                max_tokens=max(1, max_chars // 4),
                overlap_duration_seconds=0,
                overlap_segments=1 if overlap_chars > 0 else 0,
            )
        ),
    )
