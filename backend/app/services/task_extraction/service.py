from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Sequence

from app.prompts.task_extraction import build_task_extraction_prompt
from app.schemas.chunk import Chunk
from app.schemas.task import TaskItem, TaskList
from app.services.chunking.service import ChunkingService
from app.services.llm.service import LLMService, get_llm_service
from app.services.task_extraction.exceptions import (
    TaskExtractionInvalidResponseError,
    TaskExtractionLLMFailureError,
)

if TYPE_CHECKING:
    from app.models.transcript import Transcript
    from app.models.transcript_segment import TranscriptSegment

logger = logging.getLogger(__name__)


class TaskExtractionService:
    """Serviço para extração estruturada de tarefas, responsáveis e prazos."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        chunking_service: ChunkingService | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._chunking_service = chunking_service or ChunkingService()

    @property
    def llm_service(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    def extract(
        self,
        transcript: (
            Transcript | Sequence[TranscriptSegment] | Sequence[Chunk] | str | None
        ),
    ) -> list[TaskItem]:
        """Extrai tarefas acionáveis a partir de transcrição, segmentos ou chunks.

        Parâmetros:
        - transcript: objeto Transcript, sequência de TranscriptSegments,
          sequência de Chunks previamente fatiados, string pura ou None.

        Retorna:
        - list[TaskItem]: Lista de tarefas consolidadas e deduplicadas.
        """
        if transcript is None:
            return []

        # 1. Identificar ou gerar os Chunks a serem processados
        chunks: list[Chunk] = self._resolve_chunks(transcript)
        if not chunks:
            return []

        all_tasks: list[TaskItem] = []

        # 2. Processar cada chunk através do LLM
        for chunk in chunks:
            chunk_tasks = self._process_chunk(chunk)
            all_tasks.extend(chunk_tasks)

        # 3. Consolidar e tratar duplicações (ex: causadas por overlaps)
        return self._deduplicate_tasks(all_tasks)

    def _resolve_chunks(
        self,
        transcript: (Transcript | Sequence[TranscriptSegment] | Sequence[Chunk] | str),
    ) -> list[Chunk]:
        """Garante que a entrada seja convertida em uma lista de Chunks."""
        # Se já for uma sequência contendo Chunks
        if (
            isinstance(transcript, Sequence)
            and not isinstance(transcript, (str, bytes))
            and len(transcript) > 0
            and isinstance(transcript[0], Chunk)
        ):
            return list(transcript)

        # Caso contrário, utiliza o ChunkingService
        return self._chunking_service.split(transcript)

    def _process_chunk(self, chunk: Chunk) -> list[TaskItem]:
        """Envia o texto do chunk ao LLM e extrai a lista estruturada de tarefas."""
        if not chunk.text or not chunk.text.strip():
            return []

        prompt = build_task_extraction_prompt(
            transcript_text=chunk.text,
            speakers=chunk.speakers,
        )

        try:
            raw_response = self.llm_service.generate(prompt)
        except Exception as exc:
            logger.error("Falha ao comunicar com o serviço de LLM: %s", exc)
            raise TaskExtractionLLMFailureError(
                f"Erro durante chamada ao serviço de LLM: {exc}"
            ) from exc

        return self._parse_llm_response(raw_response)

    def _parse_llm_response(self, response_text: str) -> list[TaskItem]:
        """Interpreta a resposta do modelo validando contra o schema Pydantic."""
        if not response_text or not response_text.strip():
            raise TaskExtractionInvalidResponseError(
                "O modelo retornou uma resposta vazia."
            )

        clean_text = self._strip_markdown_fences(response_text.strip())

        try:
            payload = json.loads(clean_text)
        except json.JSONDecodeError as exc:
            logger.error("JSON retornado pelo LLM é inválido: %s", response_text)
            raise TaskExtractionInvalidResponseError(
                f"Resposta do modelo não é um JSON válido: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise TaskExtractionInvalidResponseError(
                "A resposta raiz do modelo deve ser um objeto JSON."
            )

        try:
            parsed = TaskList.model_validate(payload)
            return parsed.tasks
        except Exception as exc:
            logger.error("Erro de validação do schema TaskList: %s", exc)
            raise TaskExtractionInvalidResponseError(
                f"Resposta não compatível com o schema de tarefas: {exc}"
            ) from exc

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove blocos de código markdown (```json ... ```) se presentes."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text

    @classmethod
    def _deduplicate_tasks(cls, tasks: list[TaskItem]) -> list[TaskItem]:
        """Remove duplicações evidentes preservando metadados enriquecidos."""
        seen: dict[str, TaskItem] = {}
        ordered_keys: list[str] = []

        for task in tasks:
            clean_task_desc = task.task.strip()
            if not clean_task_desc:
                continue

            norm_key = cls._normalize_text(clean_task_desc)
            if not norm_key:
                continue

            clean_responsible = (
                task.responsible.strip()
                if task.responsible and task.responsible.strip()
                else None
            )
            clean_deadline = (
                task.deadline.strip()
                if task.deadline and task.deadline.strip()
                else None
            )

            if norm_key in seen:
                # Duplicação evidente: enriquecer metadados existentes
                existing = seen[norm_key]
                if not existing.responsible and clean_responsible:
                    existing.responsible = clean_responsible
                if not existing.deadline and clean_deadline:
                    existing.deadline = clean_deadline
            else:
                seen[norm_key] = TaskItem(
                    task=clean_task_desc,
                    responsible=clean_responsible,
                    deadline=clean_deadline,
                )
                ordered_keys.append(norm_key)

        return [seen[k] for k in ordered_keys]

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normaliza texto para chave de comparação (minúsculas, sem pontuação)."""
        lower = text.lower().strip()
        # Remove pontuações e caracteres especiais
        alphanumeric = re.sub(r"[^\w\s]", "", lower)
        return " ".join(alphanumeric.split())
