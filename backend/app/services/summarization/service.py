"""Serviço de orquestração da sumarização de reuniões."""

from app.prompts.summarization import build_summarization_prompt
from app.schemas.summary import SummaryResponse
from app.services.chunking import TranscriptChunker
from app.services.llm import LLMService

_NOT_FOUND = "Não identificado na transcrição."


class SummarizationService:
    """Coordena chunking, LLM, validação e consolidação."""

    def __init__(self, llm: LLMService, chunker: TranscriptChunker) -> None:
        self.llm = llm
        self.chunker = chunker

    def summarize(self, transcript: str) -> SummaryResponse:
        if not transcript or not transcript.strip():
            raise ValueError("A transcrição não pode estar vazia")

        chunks = self.chunker.split(transcript)
        if not chunks:
            raise ValueError("Não foi possível criar chunks da transcrição")

        partials = [self._summarize_chunk(chunk) for chunk in chunks]
        if len(partials) == 1:
            return partials[0]
        return self._consolidate(partials)

    def _summarize_chunk(self, chunk: str) -> SummaryResponse:
        try:
            result = self.llm.summarize(build_summarization_prompt(chunk))
            return SummaryResponse.model_validate(result)
        except Exception as exc:
            raise RuntimeError("Falha ao processar um chunk com o serviço de LLM") from exc

    def _consolidate(self, partials: list[SummaryResponse]) -> SummaryResponse:
        material = self._build_consolidation_material(partials)
        prompt = f"""Você é responsável pela consolidação final de uma reunião.

Use exclusivamente os resultados parciais abaixo. Não invente informações.
Remova duplicações evidentes e preserve informações relevantes presentes em
qualquer resultado. Não transforme sugestões em decisões.

Se nenhum resultado permitir identificar o objetivo, use exatamente:
"{_NOT_FOUND}".
Se não houver decisões explícitas, retorne decisions como [].

Retorne exatamente: objective, summary, main_points e decisions.

Resultados parciais:
---
{material}
---
"""
        try:
            result = self.llm.summarize(prompt)
            return SummaryResponse.model_validate(result)
        except Exception as exc:
            raise RuntimeError("Falha ao consolidar os resultados da reunião") from exc

    @staticmethod
    def _build_consolidation_material(partials: list[SummaryResponse]) -> str:
        seen_points: set[str] = set()
        seen_decisions: set[str] = set()
        blocks: list[str] = []

        for index, partial in enumerate(partials, start=1):
            points = []
            for point in partial.main_points:
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
        chunker=TranscriptChunker(
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        ),
    )