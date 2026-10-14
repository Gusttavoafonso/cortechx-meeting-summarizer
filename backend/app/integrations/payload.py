from __future__ import annotations

from app.models.meeting import Meeting
from app.schemas.integration import (
    MeetingIntegrationPayload,
    TaskIntegrationPayload,
)


class MeetingResultUnavailableError(ValueError):
    """A reunião ainda não possui um resultado que possa ser integrado."""


def meeting_to_integration_payload(meeting: Meeting) -> MeetingIntegrationPayload:
    """Converte o resultado persistido de uma reunião no DTO de integração."""
    summary = meeting.summary
    if summary is None or not summary.summary or not summary.summary.strip():
        raise MeetingResultUnavailableError(
            "A reunião não possui um resumo persistido para integração."
        )

    return MeetingIntegrationPayload(
        meeting_id=meeting.id,
        title=meeting.title,
        summary=summary.summary,
        objective=summary.objective,
        key_points=list(summary.key_points or []),
        decisions=list(summary.decisions or []),
        tasks=[
            TaskIntegrationPayload(
                id=task.id,
                description=task.description,
                responsible=task.responsible,
                deadline=task.deadline,
            )
            for task in meeting.tasks
        ],
        created_at=meeting.created_at,
    )
