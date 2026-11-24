"""Add user_integrations, password_reset_tokens, and meetings.processing_options."""

import sqlalchemy as sa
from alembic import op

revision = "e6b202"
down_revision = "d51a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("processing_options", sa.JSON(), nullable=True),
    )

    op.create_table(
        "user_integrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_user_integrations_user_provider"
        ),
    )
    op.create_index(
        "ix_user_integrations_user_id", "user_integrations", ["user_id"]
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_token_hash", table_name="password_reset_tokens"
    )
    op.drop_index(
        "ix_password_reset_tokens_user_id", table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")

    op.drop_index("ix_user_integrations_user_id", table_name="user_integrations")
    op.drop_table("user_integrations")

    op.drop_column("meetings", "processing_options")
