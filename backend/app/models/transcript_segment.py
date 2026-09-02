from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.transcript import Transcript


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        nullable=False,
    )

    speaker: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    start_time: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    end_time: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="segments",
    )