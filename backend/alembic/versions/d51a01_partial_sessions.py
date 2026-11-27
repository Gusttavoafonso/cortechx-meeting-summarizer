"""Persist partial recording sessions separately from final transcripts."""

import sqlalchemy as sa
from alembic import op

revision = "d51a01"
down_revision = "c2e4f6a8b0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partial_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("processed_seconds", sa.Float(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_partial_sessions_user_id", "partial_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_partial_sessions_user_id", table_name="partial_sessions")
    op.drop_table("partial_sessions")
