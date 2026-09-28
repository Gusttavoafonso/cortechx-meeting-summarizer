from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.json_type import JSONType

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class Summary(Base):

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    objective: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    key_points: Mapped[list[str]] = mapped_column(
        JSONType,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )

    decisions: Mapped[list[str]] = mapped_column(
        JSONType,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )

    # Payload estruturado completo devolvido pelo pipeline (fonte da verdade para reprocessar/auditar; inclui as tarefas como o LLM as devolveu).
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )

    # Metadados da geração: provider, modelo, versão do prompt, nº de chunks...
    generation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="summary",
    )
