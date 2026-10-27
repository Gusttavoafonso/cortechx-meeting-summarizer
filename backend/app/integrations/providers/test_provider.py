from __future__ import annotations

import logging
from typing import TextIO

from app.integrations.base import IntegrationProvider
from app.integrations.registry import register_provider
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload

logger = logging.getLogger(__name__)


@register_provider("teste")
class ProviderTeste(IntegrationProvider):
    """Provider local que exibe o payload sem chamar serviços externos."""

    name = "teste"

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream
        self.last_payload: MeetingIntegrationPayload | None = None

    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        self.last_payload = payload
        output = (
            f"[INTEGRAÇÃO TESTE] reunião={payload.meeting_id} "
            f"título={payload.title} tarefas={len(payload.tasks)}"
        )

        if self.stream is not None:
            self.stream.write(output + "\n")
        else:
            logger.info(output)

        return IntegrationResult(
            provider=self.name,
            success=True,
            metadata={
                "meeting_id": payload.meeting_id,
                "tasks_count": len(payload.tasks),
            },
        )
