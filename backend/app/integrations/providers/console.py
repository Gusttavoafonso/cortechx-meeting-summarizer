from __future__ import annotations

import logging
from typing import TextIO

from app.integrations.base import IntegrationProvider
from app.integrations.registry import register_provider
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload

logger = logging.getLogger(__name__)


@register_provider("console")
class ConsoleProvider(IntegrationProvider):
    """Provedor de desenvolvimento e teste que exibe os dados da reunião no console/log."""

    name: str = "console"

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream
        self.last_payload: MeetingIntegrationPayload | None = None

    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        """Formata e imprime a reunião sem realizar chamadas de rede."""
        self.last_payload = payload

        lines = [
            f"=== [INTEGRAÇÃO CONSOLE: Reunião #{payload.meeting_id}] ===",
            f"Título: {payload.title}",
            f"Objetivo: {payload.objective or 'Não informado'}",
            f"Resumo: {payload.summary}",
        ]

        if payload.key_points:
            lines.append("Principais Pontos:")
            for pt in payload.key_points:
                lines.append(f"  • {pt}")

        if payload.decisions:
            lines.append("Decisões:")
            for dec in payload.decisions:
                lines.append(f"  • {dec}")

        if payload.tasks:
            lines.append("Tarefas:")
            for t in payload.tasks:
                resp = f" (Responsável: {t.responsible})" if t.responsible else ""
                prazo = f" [Prazo: {t.deadline}]" if t.deadline else ""
                lines.append(f"  - {t.description}{resp}{prazo}")

        lines.append("=" * 50)
        output_text = "\n".join(lines)

        if self.stream is not None:
            self.stream.write(output_text + "\n")
        else:
            logger.info("\n%s", output_text)

        return IntegrationResult(
            provider=self.name,
            success=True,
            metadata={
                "meeting_id": payload.meeting_id,
                "tasks_count": len(payload.tasks),
                "key_points_count": len(payload.key_points),
                "decisions_count": len(payload.decisions),
            },
        )
