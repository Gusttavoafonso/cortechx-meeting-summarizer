from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment
from app.services.diarization import DiarizationAssociationError

if TYPE_CHECKING:
    from app.services.diarization import DiarizationSegment
    from app.services.transcription.base import SegmentData


class InvalidTranscriptSegmentError(ValueError):
    pass


class TranscriptRepository:
    """Repositório para persistência e recuperação de transcrições e seus segmentos."""

    TIMESTAMP_TOLERANCE_SECONDS = 0.3

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

        if commit:
            self.db.commit()
            self.db.refresh(transcript)
        else:
            self.db.flush()
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

    @staticmethod
    def _calculate_overlap(
        first_start: float,
        first_end: float,
        second_start: float,
        second_end: float,
    ) -> float:
        """Calcula a duração da interseção entre dois intervalos."""
        return max(0.0, min(first_end, second_end) - max(first_start, second_start))

    @staticmethod
    def _calculate_interval_distance(
        first_start: float,
        first_end: float,
        second_start: float,
        second_end: float,
    ) -> float:
        """Calcula o gap entre intervalos; retorna zero se eles se sobrepõem."""
        return max(0.0, second_start - first_end, first_start - second_end)

    def apply_diarization(
        self,
        transcript: Transcript,
        diarization_segments: list[DiarizationSegment],
    ) -> Transcript:
        """Associa cada segmento transcrito ao locutor com maior sobreposição."""
        assignments: list[tuple[TranscriptSegment, str]] = []
        for transcript_segment in transcript.segments:
            if (
                transcript_segment.start_time is None
                or transcript_segment.end_time is None
                or transcript_segment.end_time <= transcript_segment.start_time
            ):
                raise DiarizationAssociationError(
                    "A transcrição contém timestamps inválidos."
                )

            best_match = max(
                diarization_segments,
                key=lambda diarization_segment: self._calculate_overlap(
                    transcript_segment.start_time,
                    transcript_segment.end_time,
                    diarization_segment.start_time,
                    diarization_segment.end_time,
                ),
                default=None,
            )

            if best_match is not None and self._calculate_overlap(
                transcript_segment.start_time,
                transcript_segment.end_time,
                best_match.start_time,
                best_match.end_time,
            ) > 0:
                assignments.append((transcript_segment, best_match.speaker))
                continue

            nearest_match = min(
                diarization_segments,
                key=lambda diarization_segment: self._calculate_interval_distance(
                    transcript_segment.start_time,
                    transcript_segment.end_time,
                    diarization_segment.start_time,
                    diarization_segment.end_time,
                ),
                default=None,
            )
            if nearest_match is not None and self._calculate_interval_distance(
                transcript_segment.start_time,
                transcript_segment.end_time,
                nearest_match.start_time,
                nearest_match.end_time,
            ) <= self.TIMESTAMP_TOLERANCE_SECONDS:
                assignments.append((transcript_segment, nearest_match.speaker))
                continue

            raise DiarizationAssociationError(
                "Não foi possível associar um locutor a todos os segmentos."
            )

        for transcript_segment, speaker in assignments:
            transcript_segment.speaker = speaker

        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(transcript)
        return transcript
