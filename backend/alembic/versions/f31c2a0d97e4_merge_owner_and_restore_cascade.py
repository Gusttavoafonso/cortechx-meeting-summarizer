"""Merge ownership branches and restore cascade deletion for meeting owners."""

import sqlalchemy as sa
from alembic import op

revision = "f31c2a0d97e4"
down_revision = ("a1b2c3d4e5f6", "e6b202")
branch_labels = None
depends_on = None

FK_NAME = "fk_meetings_user_id_users"


def _set_ondelete(action: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    matches = [
        fk for fk in inspector.get_foreign_keys("meetings")
        if fk["constrained_columns"] == ["user_id"]
        and fk["referred_table"] == "users"
    ]
    if len(matches) != 1 or not matches[0].get("name"):
        raise RuntimeError("Expected one named meetings.user_id foreign key")
    current = matches[0]
    if current.get("options", {}).get("ondelete", "").upper() == action:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("meetings") as batch:
            batch.drop_constraint(current["name"], type_="foreignkey")
            batch.create_foreign_key(
                FK_NAME, "users", ["user_id"], ["id"], ondelete=action
            )
    else:
        op.drop_constraint(current["name"], "meetings", type_="foreignkey")
        op.create_foreign_key(
            FK_NAME, "meetings", "users", ["user_id"], ["id"], ondelete=action
        )


def upgrade() -> None:
    _set_ondelete("CASCADE")


def downgrade() -> None:
    _set_ondelete("RESTRICT")
