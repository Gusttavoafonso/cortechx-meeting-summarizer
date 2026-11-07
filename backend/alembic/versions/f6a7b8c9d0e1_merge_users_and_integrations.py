"""unifica as heads de usuários e de integrações

A revisão ``d4e5f6a7b8c9`` (usuários) partiu de ``f24c8e61a930`` em vez da head
corrente ``b7d3e5f1a284``, criando dois ramos. Com duas heads,
``alembic upgrade head`` falha com "Multiple head revisions are present".

Esta revisão apenas junta os dois ramos; não altera o esquema.

Revision ID: f6a7b8c9d0e1
Revises: b7d3e5f1a284, e5f6a7b8c9d0
Create Date: 2026-11-06
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = ("b7d3e5f1a284", "e5f6a7b8c9d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ponto de junção dos dois ramos: nada a aplicar."""


def downgrade() -> None:
    """Ponto de junção dos dois ramos: nada a desfazer."""
