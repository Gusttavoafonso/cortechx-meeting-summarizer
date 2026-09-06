from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.meeting import Meeting
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

    def create(self, title: str, status: str = "received") -> Meeting:
        meeting = Meeting(title=title, status=status)
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def update_status(self, meeting: Meeting, status: str) -> Meeting:
        meeting.status = status
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
