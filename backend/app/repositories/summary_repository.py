from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import EntityNotFoundError
from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.task import Task
from app.schemas.summary import SummaryResult


class SummaryMeetingNotFoundError(EntityNotFoundError, LookupError):
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

    def save_summary(
        self,
        meeting_id: int,
        *,
        objective: str | None = None,
        summary: str | None = None,
        main_points: list[str] | None = None,
        key_points: list[str] | None = None,
        decisions: list[str] | None = None,
        tasks: list[Any] | None = None,
        structured_result: dict[str, Any] | None = None,
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

        db_summary = meeting.summary
        if db_summary is None:
            db_summary = Summary()
            meeting.summary = db_summary

        points = key_points if key_points is not None else (main_points or [])

        db_summary.objective = objective
        db_summary.summary = summary
        db_summary.key_points = list(points)
        db_summary.decisions = list(decisions or [])
        db_summary.structured_result = structured_result
        db_summary.generation_metadata = generation_metadata

        task_records: list[Task] = []
        for index, item in enumerate(tasks or []):
            if isinstance(item, Task):
                item.position = index
                task_records.append(item)
            elif isinstance(item, dict):
                task_records.append(
                    Task(
                        position=index,
                        description=item.get("description", ""),
                        responsible=item.get("responsible"),
                        deadline=item.get("deadline"),
                    )
                )
            else:
                desc = getattr(item, "description", str(item))
                resp = getattr(item, "responsible", None)
                dead = getattr(item, "deadline", None)
                task_records.append(
                    Task(
                        position=index,
                        description=desc,
                        responsible=resp,
                        deadline=dead,
                    )
                )

        meeting.tasks = task_records

        if commit:
            self.db.commit()
            self.db.refresh(db_summary)
        else:
            self.db.flush()
        return db_summary

    def save_result(
        self,
        meeting_id: int,
        result: SummaryResult,
        *,
        generation_metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Summary:
        return self.save_summary(
            meeting_id=meeting_id,
            objective=result.objective,
            summary=result.summary,
            key_points=result.key_points,
            decisions=result.decisions,
            tasks=result.tasks,
            structured_result=result.model_dump(mode="json"),
            generation_metadata=generation_metadata,
            commit=commit,
        )
