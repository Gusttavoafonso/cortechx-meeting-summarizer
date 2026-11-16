"""add hashed_password and nullable google_id

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("users"):
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "hashed_password" not in columns:
            op.add_column(
                "users",
                sa.Column("hashed_password", sa.String(length=255), nullable=True),
            )
        # Permite google_id ser nullable (para usuários com login tradicional)
        op.alter_column("users", "google_id", nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("users"):
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "hashed_password" in columns:
            op.drop_column("users", "hashed_password")
        op.alter_column("users", "google_id", nullable=False)
