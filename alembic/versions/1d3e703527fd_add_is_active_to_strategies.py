"""add_is_active_to_strategies

Revision ID: 1d3e703527fd
Revises: d939403559ad
Create Date: 2026-02-05 10:02:46.702930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d3e703527fd'
down_revision: Union[str, Sequence[str], None] = 'd939403559ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active column to strategies table."""
    op.add_column(
        'strategies',
        sa.Column('is_active', sa.Boolean(), server_default=sa.text("'true'"), nullable=False)
    )
    # Barcha mavjud strategiyalarni faol qilish
    op.execute("UPDATE strategies SET is_active = true")


def downgrade() -> None:
    """Remove is_active column from strategies table."""
    op.drop_column('strategies', 'is_active')
