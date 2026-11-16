"""add is_active to users and merge heads

O histórico tinha duas heads (b7d3e5f1a284 e e5f6a7b8c9d0), o que fazia
`alembic upgrade head` falhar com "Multiple head revisions". Esta revisão as
unifica e adiciona users.is_active.

Revision ID: a9c3f7d2b158
Revises: b7d3e5f1a284, e5f6a7b8c9d0
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c3f7d2b158"
down_revision: Union[str, Sequence[str], None] = (
    "b7d3e5f1a284",
    "e5f6a7b8c9d0",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [col["name"] for col in inspector.get_columns("users")]
    if "is_active" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [col["name"] for col in inspector.get_columns("users")]
    if "is_active" in columns:
        op.drop_column("users", "is_active")
