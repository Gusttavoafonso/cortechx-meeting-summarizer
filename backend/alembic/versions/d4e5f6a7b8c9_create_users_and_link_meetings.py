"""create users table and link meetings

Revision ID: d4e5f6a7b8c9
Revises: f24c8e61a930
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "f24c8e61a930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("google_id", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("picture_url", sa.String(length=1024), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("google_id"),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    columns = [col["name"] for col in inspector.get_columns("meetings")]
    if "user_id" not in columns:
        op.add_column("meetings", sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_index("ix_meetings_user_id", "meetings", ["user_id"])
        op.create_foreign_key(
            "fk_meetings_user_id_users",
            "meetings",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("meetings")]
    if "user_id" in columns:
        op.drop_constraint("fk_meetings_user_id_users", "meetings", type_="foreignkey")
        op.drop_index("ix_meetings_user_id", table_name="meetings")
        op.drop_column("meetings", "user_id")

    if inspector.has_table("users"):
        op.drop_index("ix_users_email", table_name="users")
        op.drop_index("ix_users_google_id", table_name="users")
        op.drop_table("users")
