from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting


class MeetingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, meeting: Meeting) -> Meeting:
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        return meeting

    def get_by_id(self, meeting_id: int) -> Meeting | None:
        statement = select(Meeting).where(Meeting.id == meeting_id)

        return self.db.scalar(statement)

    def list_all(self) -> list[Meeting]:
        statement = select(Meeting).order_by(Meeting.created_at.desc())

        return list(self.db.scalars(statement).all())