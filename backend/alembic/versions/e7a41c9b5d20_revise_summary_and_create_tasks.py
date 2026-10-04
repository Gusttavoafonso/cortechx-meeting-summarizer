"""revise summary model and create tasks table

Revision ID: e7a41c9b5d20
Revises: bde868bf7908
Create Date: 2026-09-28 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7a41c9b5d20"
down_revision: Union[str, Sequence[str], None] = "bde868bf7908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    """Upgrade schema."""

    # 1. main_ideas era o texto do resumo (antigo "content"): passa a ser "summary".
    op.alter_column(
        "summaries",
        "main_ideas",
        new_column_name="summary",
        existing_type=sa.Text(),
        existing_nullable=True,
    )

    # 2. Estruturas complexas em JSONB.
    op.add_column(
        "summaries",
        sa.Column(
            "key_points",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "summaries",
        sa.Column(
            "decisions",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "summaries",
        sa.Column("generation_metadata", _jsonb(), nullable=True),
    )
    op.alter_column(
        "summaries",
        "structured_result",
        existing_type=sa.JSON(),
        type_=_jsonb(),
        existing_nullable=True,
        postgresql_using="structured_result::jsonb",
    )

    # 3. updated_at: adiciona nulo, faz backfill com created_at e só então NOT NULL.
    op.add_column(
        "summaries",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE summaries SET updated_at = created_at")
    op.alter_column(
        "summaries",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    # 4. Tarefas extraídas como entidade própria.
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("responsible", sa.String(length=255), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_meeting_id"), "tasks", ["meeting_id"], unique=False)


def downgrade() -> None:

    op.drop_index(op.f("ix_tasks_meeting_id"), table_name="tasks")
    op.drop_table("tasks")

    op.drop_column("summaries", "updated_at")

    op.alter_column(
        "summaries",
        "structured_result",
        existing_type=_jsonb(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="structured_result::json",
    )
    op.drop_column("summaries", "generation_metadata")
    op.drop_column("summaries", "decisions")
    op.drop_column("summaries", "key_points")

    op.alter_column(
        "summaries",
        "summary",
        new_column_name="main_ideas",
        existing_type=sa.Text(),
        existing_nullable=True,
    )
