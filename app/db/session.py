from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False)
LocalAsyncSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)