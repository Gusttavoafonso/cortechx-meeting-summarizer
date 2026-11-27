"""merge heads and add audio_files.duration_seconds

Revision ID: c2e4f6a8b0d1
Revises: 94f2c26da63d, a9c3f7d2b158
Create Date: 2026-11-17 19:36:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2e4f6a8b0d1"
down_revision: Union[str, Sequence[str], None] = ("94f2c26da63d", "a9c3f7d2b158")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branch heads and add duration_seconds column to audio_files."""
    op.add_column(
        "audio_files",
        sa.Column("duration_seconds", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove duration_seconds column from audio_files."""
    op.drop_column("audio_files", "duration_seconds")
