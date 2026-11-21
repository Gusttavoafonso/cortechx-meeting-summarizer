from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import InvalidPersistenceDataError
from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment

if TYPE_CHECKING:
    from app.services.transcription.base import SegmentData


class InvalidTranscriptSegmentError(InvalidPersistenceDataError, ValueError):
    pass


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
        *,
        commit: bool = True,
    ) -> Transcript:
        """Cria ou substitui a transcrição de uma reunião e seus segmentos."""
        self._validate_segments(segments)
        existing = self.get_by_meeting_id(meeting_id)

        if existing is not None:
            # Substitui o conteúdo e limpa segmentos antigos
            existing.content = content
            existing.segments.clear()
            self.db.flush()
            transcript = existing
        else:
            transcript = Transcript(
                meeting_id=meeting_id,
                content=content,
            )
            self.db.add(transcript)

        for seg in segments:
            segment_model = TranscriptSegment(
                speaker=seg.speaker,
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text,
            )
            transcript.segments.append(segment_model)

        try:
            if commit:
                self.db.commit()
                self.db.refresh(transcript)
            else:
                self.db.flush()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return transcript

    @staticmethod
    def _validate_segments(segments: list[SegmentData]) -> None:
        for segment in segments:
            if not isinstance(segment.text, str) or not segment.text.strip():
                raise InvalidTranscriptSegmentError(
                    "Os segmentos da transcrição precisam conter texto."
                )

            if segment.start is None or segment.end is None:
                raise InvalidTranscriptSegmentError(
                    "Os segmentos da transcrição precisam conter timestamps."
                )

            try:
                start_time = float(segment.start)
                end_time = float(segment.end)
            except (TypeError, ValueError) as exc:
                raise InvalidTranscriptSegmentError(
                    "Os timestamps dos segmentos são inválidos."
                ) from exc

            if (
                not math.isfinite(start_time)
                or not math.isfinite(end_time)
                or start_time < 0
                or end_time <= start_time
            ):
                raise InvalidTranscriptSegmentError(
                    "Os timestamps dos segmentos são inválidos."
                )

    def delete_by_meeting_id(self, meeting_id: int) -> bool:
        """Remove a transcrição de uma reunião se existir."""
        existing = self.get_by_meeting_id(meeting_id)
        if existing:
            self.db.delete(existing)
            self.db.commit()
            return True
        return False
