from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
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

    def create(
        self,
        meeting_or_title: Meeting | str | None = None,
        *,
        meeting: Meeting | None = None,
        title: str | None = None,
        status: str | MeetingStatus = MeetingStatus.RECEIVED,
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

        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target

    def update_status(self, meeting: Meeting, status: str | MeetingStatus, *, commit: bool = True) -> Meeting:
        meeting.status = status
        self.db.add(meeting)
        if commit:
            self.db.commit()
            self.db.refresh(meeting)
        return meeting
