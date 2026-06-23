"""merge heads

Revision ID: 5bcfb1fc7968
Revises: d4e5f6a7b8c9, i9j0k1l2m3n4
Create Date: 2026-06-23 18:53:47.821697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bcfb1fc7968'
down_revision: Union[str, Sequence[str], None] = ('d4e5f6a7b8c9', 'i9j0k1l2m3n4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
