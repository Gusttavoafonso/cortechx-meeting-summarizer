from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.task import Task
from app.schemas.summary import SummaryResult


class SummaryMeetingNotFoundError(LookupError):
    """Reunião inexistente ao tentar persistir o resultado da sumarização."""


class SummaryRepository:
    """Persistência do resultado da sumarização (Summary + Tasks)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_meeting_id(self, meeting_id: int) -> Summary | None:
        stmt = (
            select(Summary)
            .where(Summary.meeting_id == meeting_id)
            .options(selectinload(Summary.meeting).selectinload(Meeting.tasks))
        )
        return self.db.scalars(stmt).first()

    def list_tasks(self, meeting_id: int) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.meeting_id == meeting_id)
            .order_by(Task.position, Task.id)
        )
        return list(self.db.scalars(stmt).all())

    def save_result(
        self,
        meeting_id: int,
        result: SummaryResult,
        *,
        generation_metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Summary:
        stmt = (
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(selectinload(Meeting.summary), selectinload(Meeting.tasks))
        )
        meeting = self.db.scalars(stmt).first()
        if meeting is None:
            raise SummaryMeetingNotFoundError(meeting_id)

        summary = meeting.summary
        if summary is None:
            summary = Summary()
            meeting.summary = summary

        summary.objective = result.objective
        summary.summary = result.summary
        summary.key_points = list(result.key_points)
        summary.decisions = list(result.decisions)
        summary.structured_result = result.model_dump(mode="json")
        summary.generation_metadata = generation_metadata

        # delete-orphan remove as tarefas antigas no flush
        meeting.tasks = [
            Task(
                position=index,
                description=item.description,
                responsible=item.responsible,
                deadline=item.deadline,
            )
            for index, item in enumerate(result.tasks)
        ]

        if commit:
            self.db.commit()
            self.db.refresh(summary)
        else:
            self.db.flush()
        return summary
