"""add backtest_results table

Revision ID: e8f4c5a2b1d3
Revises: d939403559ad
Create Date: 2026-02-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f4c5a2b1d3'
down_revision: Union[str, None] = '1d3e703527fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'backtest_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        
        # Parametrlar
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        
        # Statistika
        sa.Column('total_signals', sa.Integer(), default=0),
        sa.Column('long_signals', sa.Integer(), default=0),
        sa.Column('short_signals', sa.Integer(), default=0),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('partial_wins', sa.Integer(), default=0),
        sa.Column('timeouts', sa.Integer(), default=0),
        
        # TP statistikasi
        sa.Column('tp1_hits', sa.Integer(), default=0),
        sa.Column('tp2_hits', sa.Integer(), default=0),
        sa.Column('tp3_hits', sa.Integer(), default=0),
        
        # Profit statistikasi
        sa.Column('total_profit', sa.Float(), default=0.0),
        sa.Column('average_profit', sa.Float(), default=0.0),
        sa.Column('average_loss', sa.Float(), default=0.0),
        sa.Column('max_profit', sa.Float(), default=0.0),
        sa.Column('max_loss', sa.Float(), default=0.0),
        sa.Column('profit_factor', sa.Float(), default=0.0),
        sa.Column('win_rate', sa.Float(), default=0.0),
        
        # Trade ma'lumotlari (JSON)
        sa.Column('trades_json', sa.Text(), nullable=True),
        
        # PDF file path
        sa.Column('pdf_path', sa.String(500), nullable=True),
        
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indekslar
    op.create_index(
        'ix_backtest_user_params',
        'backtest_results',
        ['user_id', 'symbol', 'timeframe', 'threshold', 'start_date', 'end_date']
    )
    op.create_index('ix_backtest_user_id', 'backtest_results', ['user_id'])
    op.create_index('ix_backtest_created_at', 'backtest_results', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_backtest_created_at', table_name='backtest_results')
    op.drop_index('ix_backtest_user_id', table_name='backtest_results')
    op.drop_index('ix_backtest_user_params', table_name='backtest_results')
    op.drop_table('backtest_results')
