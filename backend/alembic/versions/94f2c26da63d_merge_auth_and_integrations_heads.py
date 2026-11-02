"""merge_auth_and_integrations_heads

Revision ID: 94f2c26da63d
Revises: b7d3e5f1a284, e5f6a7b8c9d0
Create Date: 2026-11-02 19:51:50.807550

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94f2c26da63d'
down_revision: Union[str, Sequence[str], None] = ('b7d3e5f1a284', 'e5f6a7b8c9d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
