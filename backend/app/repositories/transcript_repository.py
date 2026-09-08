from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment

if TYPE_CHECKING:
    from app.services.transcription.base import SegmentData


class TranscriptRepository:
    """Repositório para persistência e recuperação de transcrições e seus segmentos."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_meeting_id(self, meeting_id: int) -> Transcript | None:
        """Obtém a transcrição associada a uma reunião pelo seu identificador."""
        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting_id)
            .options(selectinload(Transcript.segments))
        )
        return self.db.scalars(stmt).first()

    def save_transcript(
        self,
        meeting_id: int,
        content: str,
        segments: list[SegmentData],
    ) -> Transcript:
        """Cria ou substitui a transcrição de uma reunião e seus segmentos."""
        existing = self.get_by_meeting_id(meeting_id)

        if existing is not None:
            # Substitui o conteúdo e limpa segmentos antigos
            existing.content = content
            existing.segments.clear()
            transcript = existing
        else:
            transcript = Transcript(
                meeting_id=meeting_id,
                content=content,
            )
            self.db.add(transcript)

        for seg in segments:
            segment_model = TranscriptSegment(
                transcript=transcript,
                speaker=seg.speaker,
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text,
            )
            transcript.segments.append(segment_model)

        self.db.commit()
        self.db.refresh(transcript)
        return transcript

    def delete_by_meeting_id(self, meeting_id: int) -> bool:
        """Remove a transcrição de uma reunião se existir."""
        existing = self.get_by_meeting_id(meeting_id)
        if existing:
            self.db.delete(existing)
            self.db.commit()
            return True
        return False
