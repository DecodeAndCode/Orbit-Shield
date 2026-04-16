"""Shared test fixtures for Collider backend tests."""

import pytest_asyncio
from sqlalchemy import BigInteger, Integer, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.models import Base, Satellite, OrbitalElement, Conjunction, CDMHistory

# Tables that are SQLite-compatible (or made compatible via type overrides below)
_SQLITE_TABLES = [
    Satellite.__table__,
    OrbitalElement.__table__,
    Conjunction.__table__,
    CDMHistory.__table__,
]


def _use_integer_for_bigint(conn, cursor, statement, parameters, context, executemany):
    """No-op: BigInteger DDL is handled at create_all time via listen."""


def _sqlite_bigint_ddl(target, connection, **kw):
    """SQLite-specific: BigInteger columns need INTEGER for autoincrement to work."""


@pytest_asyncio.fixture
async def db_session():
    """In-memory async database session for testing.

    Uses SQLite for speed. Only creates SQLite-compatible tables
    (satellites, orbital_elements, conjunctions). For PostgreSQL-specific
    features (JSONB, ARRAY) use a test PostgreSQL instance via docker-compose.

    BigInteger PKs are mapped to Integer so SQLite autoincrement works.
    """
    # Patch BigInteger columns to Integer for SQLite DDL
    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    # Override BigInteger rendering for SQLite: visit_BIGINT → INTEGER
    orig_bigint = sqlite_dialect.base.SQLiteTypeCompiler.visit_BIGINT

    def _visit_bigint(self, type_, **kw):
        return "INTEGER"

    # Override JSONB rendering for SQLite: JSONB → TEXT
    orig_jsonb = getattr(sqlite_dialect.base.SQLiteTypeCompiler, "visit_JSONB", None)

    def _visit_jsonb(self, type_, **kw):
        return "TEXT"

    sqlite_dialect.base.SQLiteTypeCompiler.visit_BIGINT = _visit_bigint
    sqlite_dialect.base.SQLiteTypeCompiler.visit_JSONB = _visit_jsonb

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=_SQLITE_TABLES
            )
        )

    # Restore originals
    sqlite_dialect.base.SQLiteTypeCompiler.visit_BIGINT = orig_bigint
    if orig_jsonb is None:
        del sqlite_dialect.base.SQLiteTypeCompiler.visit_JSONB
    else:
        sqlite_dialect.base.SQLiteTypeCompiler.visit_JSONB = orig_jsonb

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.drop_all(
                sync_conn, tables=_SQLITE_TABLES
            )
        )
    await engine.dispose()
