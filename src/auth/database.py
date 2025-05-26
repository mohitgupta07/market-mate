from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os
from typing import AsyncGenerator
# Use absolute path for SQLite database
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.dirname(__file__)}/../test.db"

engine = create_async_engine(DATABASE_URL, echo=True)
# SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Create async session factory
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass


# Dependency to get async session
# async def get_db():
#     async with SessionLocal() as session:
#         yield session
#

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session