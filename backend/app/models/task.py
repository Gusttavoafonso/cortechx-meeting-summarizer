from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class Task(Base):

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ordem original devolvida pelo pipeline (estável para exibição/integrações).
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    responsible: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Data resolvida. Prazos que o pipeline não conseguiu resolver para uma data ficam nulos
    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="tasks",
    )
