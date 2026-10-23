from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


# Conversão de uma reunião para o formato da API do Notion.
# O formatter não faz requisições: ele só traduz o schema interno em
# properties da database e blocos de conteúdo da página.
class NotionFormatter:
    # Cada item de rich_text aceita no máximo 2.000 caracteres.
    text_limit = 2_000
    default_status = "Pendente"
    unassigned_label = "Sem responsável"

    # Properties da linha criada na database.
    def properties(self, payload: MeetingIntegrationPayload) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "Name": {"title": self._rich_text(payload.title.strip())},
            "meeting_id": {"number": payload.meeting_id},
            "Status": {"select": {"name": self.default_status}},
        }

        if payload.created_at is not None:
            properties["Data"] = {
                "date": {"start": payload.created_at.date().isoformat()}
            }

        return properties

    # Blocos de conteúdo do corpo da página, na ordem de leitura.
    def blocks(self, payload: MeetingIntegrationPayload) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []

        if objective := self._text(payload.objective):
            blocks.append(self._heading("Objetivo"))
            blocks.extend(self._paragraphs(objective))

        blocks.append(self._heading("Resumo"))
        blocks.extend(self._paragraphs(payload.summary.strip()))

        blocks.extend(self._list_section("Principais pontos", payload.key_points))
        blocks.extend(self._list_section("Decisões", payload.decisions))
        blocks.extend(self._task_section(payload.tasks))

        return blocks

    def _list_section(
        self,
        title: str,
        items: Iterable[str],
    ) -> list[dict[str, Any]]:
        bullets = [self._bullet(text) for item in items if (text := self._text(item))]
        return [self._heading(title), *bullets] if bullets else []

    # As tarefas são agrupadas por responsável, como na issue #31.
    def _task_section(
        self,
        tasks: Iterable[TaskIntegrationPayload],
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[TaskIntegrationPayload]] = {}

        for task in tasks:
            if not self._text(task.description):
                continue
            responsible = self._text(task.responsible) or self.unassigned_label
            groups.setdefault(responsible, []).append(task)

        if not groups:
            return []

        blocks = [self._heading("Tarefas")]
        for responsible, group in groups.items():
            blocks.append(self._subheading(responsible))
            blocks.extend(self._bullet(self._task_line(task)) for task in group)

        return blocks

    # O prazo fica na mesma linha da tarefa para não perder a associação
    # quando um responsável tem mais de uma tarefa.
    def _task_line(self, task: TaskIntegrationPayload) -> str:
        description = task.description.strip()

        if task.deadline is not None and (
            deadline_str := self._format_deadline(task.deadline)
        ):
            return f"{description} — Prazo: {deadline_str}"

        return description

    def _heading(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": self._rich_text(text)},
        }

    def _subheading(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": self._rich_text(text)},
        }

    def _bullet(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": self._rich_text(text)},
        }

    # Texto longo vira vários parágrafos, em vez de ser cortado.
    def _paragraphs(self, text: str) -> list[dict[str, Any]]:
        return [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                },
            }
            for chunk in self._chunks(text)
        ]

    @classmethod
    def _rich_text(cls, value: str | None) -> list[dict[str, Any]]:
        return [
            {"type": "text", "text": {"content": chunk}}
            for chunk in cls._chunks(value or "")
        ]

    @classmethod
    def _chunks(cls, text: str) -> list[str]:
        if not text:
            return []
        return [
            text[index : index + cls.text_limit]
            for index in range(0, len(text), cls.text_limit)
        ]

    @staticmethod
    def _text(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @staticmethod
    def _format_deadline(deadline: date | str) -> str:
        if isinstance(deadline, datetime):
            return deadline.date().isoformat()
        if isinstance(deadline, date):
            return deadline.isoformat()
        return str(deadline).strip()
