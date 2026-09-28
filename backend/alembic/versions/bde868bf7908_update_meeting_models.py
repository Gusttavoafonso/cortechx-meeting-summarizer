"""update meeting models

Revision ID: bde868bf7908
Revises: c1a7d2e3f4b5
Create Date: 2026-09-05 21:51:57.942763
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "bde868bf7908"
down_revision: Union[str, Sequence[str], None] = "c1a7d2e3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


meeting_status_enum = postgresql.ENUM(
    "received",
    "audio_uploaded",
    "transcribing",
    "transcribed",
    "processing",
    "completed",
    "failed",
    name="meeting_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        meeting_status_enum.create(
            bind,
            checkfirst=True,
        )

        op.execute(
            """
            UPDATE meetings
            SET status = LOWER(status)
            """
        )

        op.alter_column(
            "meetings",
            "status",
            existing_type=sa.VARCHAR(length=50),
            type_=meeting_status_enum,
            existing_nullable=False,
            postgresql_using="status::meeting_status",
        )

    op.alter_column(
        "summaries",
        "content",
        new_column_name="main_ideas",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    op.alter_column(
        "summaries",
        "main_ideas",
        existing_type=sa.Text(),
        nullable=True,
    )

    op.add_column(
        "summaries",
        sa.Column(
            "objective",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "summaries",
        sa.Column(
            "structured_result",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.alter_column(
        "transcripts",
        "content",
        new_column_name="raw_text",
        existing_type=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.alter_column(
        "transcripts",
        "raw_text",
        new_column_name="content",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    op.drop_column(
        "summaries",
        "structured_result",
    )

    op.drop_column(
        "summaries",
        "objective",
    )

    op.execute(
        """
        UPDATE summaries
        SET main_ideas = ''
        WHERE main_ideas IS NULL
        """
    )

    op.alter_column(
        "summaries",
        "main_ideas",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.alter_column(
        "summaries",
        "main_ideas",
        new_column_name="content",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "meetings",
            "status",
            existing_type=meeting_status_enum,
            type_=sa.VARCHAR(length=50),
            existing_nullable=False,
            postgresql_using="status::text",
        )

        meeting_status_enum.drop(
            bind,
            checkfirst=True,
        )