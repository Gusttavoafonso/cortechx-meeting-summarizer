"""troca o FK meetings.user_id para ondelete RESTRICT

Com ``CASCADE``, apagar um usuário removeria as linhas das reuniões mas **não**
os áudios já gravados em disco, que ficariam órfãos e sem referência. Com
``RESTRICT``, o banco barra a exclusão de um usuário que ainda tenha reuniões
(ver docs/autenticacao.md).

A coluna continua nullable: as reuniões anteriores ao controle de posse seguem
sem dono e, por isso, inacessíveis pela API. Nenhuma linha é reescrita, então a
migration não falha em bancos com dados existentes.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_meetings_user_id_users"


def _existing_user_fk(inspector: sa.Inspector) -> str | None:
    """Nome da FK de meetings.user_id para users, se já existir."""
    for fk in inspector.get_foreign_keys("meetings"):
        if fk.get("referred_table") == "users" and fk.get("constrained_columns") == [
            "user_id"
        ]:
            return fk.get("name")
    return None


def _recreate_fk(ondelete: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("meetings") or not inspector.has_table("users"):
        return
    if "user_id" not in [col["name"] for col in inspector.get_columns("meetings")]:
        return

    current = _existing_user_fk(inspector)

    # SQLite não altera constraints no lugar: o batch recria a tabela.
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("meetings") as batch:
            if current:
                batch.drop_constraint(current, type_="foreignkey")
            batch.create_foreign_key(
                FK_NAME, "users", ["user_id"], ["id"], ondelete=ondelete
            )
        return

    if current:
        op.drop_constraint(current, "meetings", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME, "meetings", "users", ["user_id"], ["id"], ondelete=ondelete
    )


def upgrade() -> None:
    _recreate_fk("RESTRICT")


def downgrade() -> None:
    _recreate_fk("CASCADE")
