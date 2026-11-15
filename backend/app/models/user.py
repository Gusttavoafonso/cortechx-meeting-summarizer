from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.meeting import Meeting


def normalize_email(email: str) -> str:
    """Normaliza o e-mail (trim + minúsculas) antes de salvar e consultar."""
    return email.strip().lower()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    google_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    picture_url: Mapped[str | None] = mapped_column(
        String(1024),
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

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)

    meetings: Mapped[list[Meeting]] = relationship(
        "Meeting",
        back_populates="user",
        cascade="all, delete-orphan",
    )
