"""SQLite database engine and session management."""

import os
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DB_PATH = os.environ.get("DB_PATH", "/data/kennel.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"
SYNC_DB_URL = f"sqlite:///{DB_PATH}"

async_engine = create_async_engine(DB_URL, echo=False)
sync_engine = create_engine(SYNC_DB_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_db_and_tables() -> None:
    """Create all tables from SQLModel metadata (used in tests and first-run)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
