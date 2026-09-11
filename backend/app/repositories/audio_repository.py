from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audio_file import AudioFile


class AudioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_meeting_id(self, meeting_id: int) -> AudioFile | None:
        statement = select(AudioFile).where(AudioFile.meeting_id == meeting_id)
        return self.db.scalars(statement).first()

    def save_audio_metadata(
        self,
        meeting_id: int,
        original_filename: str,
        filename: str,
        file_path: str,
        content_type: str,
        file_size_bytes: int,
    ) -> AudioFile:
        from datetime import datetime, timezone

        safe_original = original_filename[:255]
        safe_filename = filename[:255]

        existing = self.get_by_meeting_id(meeting_id)
        if existing:
            existing.original_filename = safe_original
            existing.filename = safe_filename
            existing.file_path = file_path
            existing.content_type = content_type
            existing.file_size_bytes = file_size_bytes
            existing.created_at = datetime.now(timezone.utc)
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        audio_file = AudioFile(
            meeting_id=meeting_id,
            original_filename=safe_original,
            filename=safe_filename,
            file_path=file_path,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
        )
        self.db.add(audio_file)
        self.db.commit()
        self.db.refresh(audio_file)
        return audio_file
