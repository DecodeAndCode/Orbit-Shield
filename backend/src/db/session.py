"""Async database session management using SQLAlchemy 2.0."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,  # check liveness before use; reconnects dead connections silently
    pool_recycle=300,  # drop connections older than 5 min (Neon kills idle conns)
    connect_args={
        "timeout": 30,  # asyncpg connect timeout (default 10s) — Neon cold-start can exceed
        "server_settings": {"jit": "off"},  # Neon recommends; faster small queries
    },
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
