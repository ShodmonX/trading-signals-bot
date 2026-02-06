"""add strategy performance weight and backtest performance json

Revision ID: f4b1c2d3e4f5
Revises: e8f4c5a2b1d3
Create Date: 2026-02-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4b1c2d3e4f5'
down_revision: Union[str, None] = 'e8f4c5a2b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'strategies',
        sa.Column('performance_weight', sa.Float(), server_default='1.0', nullable=False)
    )
    op.add_column(
        'backtest_results',
        sa.Column('strategy_performance_json', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('backtest_results', 'strategy_performance_json')
    op.drop_column('strategies', 'performance_weight')
