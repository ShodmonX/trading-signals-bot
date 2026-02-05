from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings


settings = get_settings()
engine = create_async_engine(settings.DATABASE_URL, echo=False)
LocalAsyncSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session():
    """Async context manager for database sessions"""
    session = LocalAsyncSession()
    try:
        yield session
    finally:
        await session.close()