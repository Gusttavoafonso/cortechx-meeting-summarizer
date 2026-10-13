"""Add processing timestamps and last error to meetings.

Revision ID: a62f3d9c1b20
Revises: f24c8e61a930
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "a62f3d9c1b20"
down_revision = "f24c8e61a930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("meetings", sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("meetings", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("meetings", "last_error")
    op.drop_column("meetings", "processing_completed_at")
    op.drop_column("meetings", "processing_started_at")
