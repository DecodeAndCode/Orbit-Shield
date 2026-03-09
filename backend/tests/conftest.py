"""Shared test fixtures for Collider backend tests."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.models import Base


@pytest_asyncio.fixture
async def db_session():
    """In-memory async database session for testing.

    Uses SQLite for speed. For PostgreSQL-specific features (JSONB, ARRAY),
    use a test PostgreSQL instance via docker-compose.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
