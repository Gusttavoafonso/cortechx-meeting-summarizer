from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


# Conversão de uma reunião para o formato de mensagem do Discord.
# O limite de 2.000 caracteres é respeitado, sem descartar texto.
# Linhas acima desse limite são divididas em blocos menores.
class DiscordFormatter:
    max_message_length = 2_000

    # Retorna blocos de mensagem para o Discord.
    def format(self, payload: MeetingIntegrationPayload) -> list[str]:
        sections = [
            f"## Reunião: {payload.title.strip()}",
            "",
            "### Resumo",
            payload.summary.strip(),
        ]

        if objective := self._text(payload.objective):
            sections.extend(["", "### Objetivo", objective])

        sections.extend(self._list_section("Principais pontos", payload.key_points))
        sections.extend(self._list_section("Decisões", payload.decisions))
        sections.extend(self._task_section(payload.tasks))

        return self._split("\n".join(sections))

    def _list_section(self, title: str, items: Iterable[str]) -> list[str]:
        lines = [f"- {text}" for item in items if (text := self._text(item))]
        return ["", f"### {title}", *lines] if lines else []

    def _task_section(self, tasks: Iterable[TaskIntegrationPayload]) -> list[str]:
        lines = [self._format_task(task) for task in tasks]
        return ["", "### Tarefas", *lines] if lines else []

    def _format_task(self, task: TaskIntegrationPayload) -> str:
        details: list[str] = []
        if responsible := self._text(task.responsible):
            details.append(f"Responsável: {responsible}")
        if task.deadline is not None:
            details.append(f"Prazo: {self._format_deadline(task.deadline)}")

        suffix = f" ({' | '.join(details)})" if details else ""
        return f"- [ ] {task.description.strip()}{suffix}"

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
        return deadline.strip()

    def _split(self, content: str) -> list[str]:
        """Divide por linhas quando possível e nunca descarta texto acima do limite."""
        chunks: list[str] = []
        current = ""

        for line in content.splitlines():
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) <= self.max_message_length:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            while len(line) > self.max_message_length:
                chunks.append(line[: self.max_message_length])
                line = line[self.max_message_length :]
            current = line

        if current:
            chunks.append(current)
        return chunks
