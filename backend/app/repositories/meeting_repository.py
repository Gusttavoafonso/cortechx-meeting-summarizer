from datetime import datetime, timezone

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.audio_file import AudioFile
from app.models.meeting import Meeting
from app.models.meeting_status import IN_PROGRESS_STATUSES, MeetingStatus
from app.models.task import Task
from app.models.transcript import Transcript


class MeetingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, meeting_id: int) -> Meeting | None:
        statement = (
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(
                selectinload(Meeting.audio),
                selectinload(Meeting.transcript).selectinload(Transcript.segments),
            )
        )
        return self.db.scalars(statement).first()

    def get_by_id_and_user(self, meeting_id: int, user_id: int) -> Meeting | None:
        statement = (
            select(Meeting)
            .where(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id,
            )
            .options(
                selectinload(Meeting.audio),
                selectinload(Meeting.summary),
                selectinload(Meeting.tasks),
                selectinload(Meeting.transcript).selectinload(Transcript.segments),
            )
        )
        return self.db.scalars(statement).first()

    def list_all(self) -> list[Meeting]:
        statement = (
            select(Meeting)
            .options(
                selectinload(Meeting.audio),
                selectinload(Meeting.transcript).selectinload(Transcript.segments),
            )
            .order_by(Meeting.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def list_by_user(self, user_id: int) -> list[Meeting]:
        statement = (
            select(Meeting)
            .where(Meeting.user_id == user_id)
            .options(
                selectinload(Meeting.audio),
                selectinload(Meeting.summary),
                selectinload(Meeting.tasks),
            )
            .order_by(Meeting.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def delete(self, meeting: Meeting) -> None:
        self.db.delete(meeting)
        self.db.commit()

    def get_stats_by_user(self, user_id: int) -> dict:
        in_progress_values = [s.value for s in IN_PROGRESS_STATUSES]
        counts_row = self.db.execute(
            select(
                func.count(Meeting.id),
                func.coalesce(
                    func.sum(
                        case(
                            (Meeting.status == MeetingStatus.COMPLETED, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (Meeting.status.in_(in_progress_values), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (Meeting.status == MeetingStatus.FAILED, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(Meeting.user_id == user_id)
        ).one()

        total_audio_seconds = self.db.scalar(
            select(func.coalesce(func.sum(AudioFile.duration_seconds), 0.0))
            .join(Meeting, AudioFile.meeting_id == Meeting.id)
            .where(Meeting.user_id == user_id)
        )
        total_tasks = self.db.scalar(
            select(func.count(Task.id))
            .join(Meeting, Task.meeting_id == Meeting.id)
            .where(Meeting.user_id == user_id)
        )
        recent_meetings = list(
            self.db.scalars(
                select(Meeting)
                .where(Meeting.user_id == user_id)
                .options(
                    selectinload(Meeting.audio),
                    selectinload(Meeting.summary),
                    selectinload(Meeting.tasks),
                )
                .order_by(Meeting.created_at.desc(), Meeting.id.desc())
                .limit(5)
            ).all()
        )
        return {
            "total_meetings": int(counts_row[0] or 0),
            "completed_meetings": int(counts_row[1] or 0),
            "processing_meetings": int(counts_row[2] or 0),
            "failed_meetings": int(counts_row[3] or 0),
            "total_audio_seconds": float(total_audio_seconds or 0.0),
            "total_tasks": int(total_tasks or 0),
            "recent_meetings": recent_meetings,
        }

    def list_tasks_by_user(
        self, user_id: int
    ) -> list[tuple[Task, str, MeetingStatus]]:
        stmt = (
            select(Task, Meeting.title, Meeting.status)
            .join(Meeting, Task.meeting_id == Meeting.id)
            .where(Meeting.user_id == user_id)
            .order_by(
                Meeting.created_at.desc(),
                Meeting.id.desc(),
                Task.position.asc(),
                Task.id.asc(),
            )
        )
        return [
            (row[0], row[1], row[2])
            for row in self.db.execute(stmt).all()
        ]

    def create(
        self,
        meeting_or_title: Meeting | str | None = None,
        *,
        meeting: Meeting | None = None,
        title: str | None = None,
        status: str | MeetingStatus = MeetingStatus.RECEIVED,
        user_id: int | None = None,
    ) -> Meeting:
        if isinstance(meeting_or_title, Meeting):
            target = meeting_or_title
        elif isinstance(meeting_or_title, str):
            target = Meeting(title=meeting_or_title, status=status)
        elif meeting is not None:
            target = meeting
        elif title is not None:
            target = Meeting(title=title, status=status)
        else:
            raise ValueError("Either a Meeting instance or title must be provided.")

        if user_id is not None and target.user_id is None:
            target.user_id = user_id

        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target

    def update_status(
        self,
        meeting: Meeting,
        status: str | MeetingStatus,
        *,
        commit: bool = True,
    ) -> Meeting:
        meeting.status = status
        self.db.add(meeting)
        try:
            if commit:
                self.db.commit()
                self.db.refresh(meeting)
            else:
                self.db.flush()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return meeting

    def try_claim_processing(self, meeting_id: int) -> bool:
        """Adquire atomicamente o lock de processamento via UPDATE condicional."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Meeting)
            .where(
                Meeting.id == meeting_id,
                Meeting.status.notin_(
                    [MeetingStatus.PROCESSING, MeetingStatus.TRANSCRIBING]
                ),
            )
            .values(
                status=MeetingStatus.PROCESSING,
                processing_started_at=now,
                processing_completed_at=None,
                last_error=None,
                updated_at=now,
            )
        )
        try:
            result = self.db.execute(stmt)
            self.db.commit()
            return bool(result.rowcount and result.rowcount > 0)
        except SQLAlchemyError:
            self.db.rollback()
            raise
