"""seed: criptos and strategies

Revision ID: dd1a5b3aa478
Revises: 9b6938b862f6
Create Date: 2026-02-05 09:32:29.074518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd1a5b3aa478'
down_revision: Union[str, Sequence[str], None] = '9b6938b862f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Seed data
cryptos = [
    {"name": "Bitcoin", "symbol": "BTCUSDT"},
    {"name": "Ethereum", "symbol": "ETHUSDT"},
    {"name": "Binance Coin", "symbol": "BNBUSDT"},
    {"name": "Solana", "symbol": "SOLUSDT"},
    {"name": "Avalanche", "symbol": "AVAXUSDT"},
    {"name": "XRP", "symbol": "XRPUSDT"},
    {"name": "Dogecoin", "symbol": "DOGEUSDT"},
    {"name": "Chainlink", "symbol": "LINKUSDT"},
    {"name": "Cardano", "symbol": "ADAUSDT"},
    {"name": "Toncoin", "symbol": "TONUSDT"},
]

strategies = [
    {"name": "RSI Crossover", "code": "rsicrossoverstrategy"},
    {"name": "Trend Follow", "code": "trendfollowstrategy"},
    {"name": "MACD Crossover", "code": "macdcrossoverstrategy"},
    {"name": "Bollinger Band Squeeze", "code": "bollingerbandsqueezestrategy"},
    {"name": "Stochastic Oscillator", "code": "stochasticoscillatorstrategy"},
    {"name": "SMA Crossover", "code": "smacrossoverstrategy"},
    {"name": "Williams Fractals", "code": "williamsfractalsstrategy"},
]


def upgrade() -> None:
    """Seed cryptos and strategies tables."""
    # Cryptos jadvaliga ma'lumot qo'shish
    cryptos_table = sa.table(
        'cryptos',
        sa.column('name', sa.String),
        sa.column('symbol', sa.String),
    )
    op.bulk_insert(cryptos_table, cryptos)
    
    # Strategies jadvaliga ma'lumot qo'shish
    strategies_table = sa.table(
        'strategies',
        sa.column('name', sa.String),
        sa.column('code', sa.String),
    )
    op.bulk_insert(strategies_table, strategies)


def downgrade() -> None:
    """Remove seeded data."""
    # Cryptos dan ma'lumotlarni o'chirish
    op.execute(
        sa.text("DELETE FROM cryptos WHERE symbol IN :symbols").bindparams(
            symbols=tuple(c['symbol'] for c in cryptos)
        )
    )
    
    # Strategies dan ma'lumotlarni o'chirish
    op.execute(
        sa.text("DELETE FROM strategies WHERE code IN :codes").bindparams(
            codes=tuple(s['code'] for s in strategies)
        )
    )

