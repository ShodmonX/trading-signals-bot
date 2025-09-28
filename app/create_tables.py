import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from app.db import Base, engine
from app.db.models import Crypto, Strategy
from app.db.session import LocalAsyncSession

criptos = [
    {
        "name": "Bitcoin",
        "symbol": "BTCUSDT"
    },
    {
        "name": "Ethereum",
        "symbol": "ETHUSDT"
    },
    {
        "name": "Binance Coin",
        "symbol": "BNBUSDT"
    },
    {
        "name": "Solana",
        "symbol": "SOLUSDT"
    },
    {
        "name": "Avalanche",
        "symbol": "AVAXUSDT"
    },
    {
        "name": "XRP",
        "symbol": "XRPUSDT"
    },
    {
        "name": "Dogecoin",
        "symbol": "DOGEUSDT"
    },
    {
        "name": "Chainlink",
        "symbol": "LINKUSDT"
    },
    {
        "name": "Cardano",
        "symbol": "ADAUSDT"
    },
    {
        "name": "Toncoin",
        "symbol": "TONUSDT"
    }
]

strategies = [
    {
        "name": "RSI Crossover",
        "code": "rsicrossoverstrategy"
    },
    {
        "name": "Trend Follow",
        "code": "trendfollowstrategy"
    },
    {
        "name": "MACD Crossover",
        "code": "macdcrossoverstrategy"
    },
    {
        "name": "Bollinger Band Squeeze",
        "code": "bollingerbandsqueezestrategy"
    },
    {
        "name": "Stochastic Oscillator",
        "code": "stochasticoscillatorstrategy"
    },
    {
        "name": "SMA Crossover",
        "code": "smacrossoverstrategy"
    },
    {
        "name": "Williams Fractals",
        "code": "williamsfractalsstrategy"
    }
]

async def seed_criptos():
    async with LocalAsyncSession() as session:
        for cripto in criptos:
            exists = await session.scalar(
                select(Crypto).where(Crypto.symbol == cripto["symbol"])
            )
            if not exists:
                cripto = Crypto(**cripto)
                session.add(cripto)
        await session.commit()

async def seed_strategies():
    async with LocalAsyncSession() as session:
        for strategy in strategies:
            exists = await session.scalar(
                select(Strategy).where(Strategy.code == strategy["code"])
            )
            if not exists:
                strategy = Strategy(**strategy)
                session.add(strategy)
        await session.commit()

async def create_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)   # ixtiyoriy: eskilarni o'chirish
        await conn.run_sync(Base.metadata.create_all)

async def main():
    await create_all_tables()
    await seed_criptos()
    await seed_strategies()

if __name__ == "__main__":
    asyncio.run(main())