"""add_ensemble_strategy

Revision ID: d939403559ad
Revises: dd1a5b3aa478
Create Date: 2026-02-05 09:53:42.044947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd939403559ad'
down_revision: Union[str, Sequence[str], None] = 'dd1a5b3aa478'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ensemble strategy for aggregated signals."""
    op.execute("""
        INSERT INTO strategies (name, code)
        VALUES ('Ensemble Strategy', 'ensemble')
        ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove ensemble strategy."""
    op.execute("DELETE FROM strategies WHERE code = 'ensemble';")
