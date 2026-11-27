from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime

from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


# Conversão de uma reunião para uma nota Markdown do Obsidian.
# Função pura (sem acesso a disco), reutilizável por um futuro endpoint de exportação.
class ObsidianFormatter:
    # Retorna o conteúdo completo da nota, terminado por uma única quebra de linha.
    def format(self, payload: MeetingIntegrationPayload) -> str:
        title = self._inline(payload.title)
        lines = self._frontmatter(payload, title)
        lines.extend(["", f"# {title}"])

        if objective := self._inline(payload.objective):
            lines.extend(["", "## Objetivo", objective])

        lines.extend(["", "## Resumo", payload.summary.strip()])
        lines.extend(self._list_section("Pontos principais", payload.key_points))
        lines.extend(self._list_section("Decisões", payload.decisions))
        lines.extend(self._task_section(payload.tasks))

        return "\n".join(lines).rstrip() + "\n"

    def _frontmatter(self, payload: MeetingIntegrationPayload, title: str) -> list[str]:
        lines = [
            "---",
            f"meeting_id: {payload.meeting_id}",
            # JSON entre aspas duplas é YAML válido e escapa aspas e dois-pontos.
            f"title: {json.dumps(title, ensure_ascii=False)}",
        ]
        if payload.created_at is not None:
            lines.append(f"date: {payload.created_at.date().isoformat()}")
        lines.extend(["tags: [reuniao]", "---"])
        return lines

    def _list_section(self, title: str, items: Iterable[str]) -> list[str]:
        lines = [f"- {text}" for item in items if (text := self._inline(item))]
        return ["", f"## {title}", *lines] if lines else []

    def _task_section(self, tasks: Iterable[TaskIntegrationPayload]) -> list[str]:
        lines = [
            self._format_task(task) for task in tasks if self._inline(task.description)
        ]
        return ["", "## Tarefas", *lines] if lines else []

    def _format_task(self, task: TaskIntegrationPayload) -> str:
        line = f"- [ ] {self._inline(task.description)}"
        if responsible := self._inline(task.responsible):
            line += f" — {responsible}"
        if task.deadline is not None:
            line += self._format_deadline(task.deadline)
        return line

    @staticmethod
    def _format_deadline(deadline: date | str) -> str:
        # O emoji 📅 só é usado com data ISO válida, que é o que o plugin Tasks lê.
        if isinstance(deadline, datetime):
            return f" 📅 {deadline.date().isoformat()}"
        if isinstance(deadline, date):
            return f" 📅 {deadline.isoformat()}"
        text = ObsidianFormatter._inline(deadline)
        if not text:
            return ""
        try:
            return f" 📅 {date.fromisoformat(text).isoformat()}"
        except ValueError:
            return f" (prazo: {text})"

    @staticmethod
    def _inline(value: str | None) -> str:
        # Colapsa quebras de linha para o texto não criar cabeçalhos ou itens extras.
        return " ".join(value.split()) if value else ""
