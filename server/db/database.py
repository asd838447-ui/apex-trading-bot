"""
APEX Trading Bot – Async database engine & session management.

Supports PostgreSQL (asyncpg) and SQLite (aiosqlite) via SQLAlchemy 2.0.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from server.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    url = settings.DATABASE_URL

    # Adjust pool for PostgreSQL vs SQLite
    is_sqlite = url.startswith("sqlite")
    kwargs: dict = {
        "echo": settings.DEBUG,
        "future": True,
    }
    if not is_sqlite:
        kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)

    logger.info("Creating async engine for %s", url.split("@")[-1] if "@" in url else url)
    return create_async_engine(url, **kwargs)


def get_engine() -> AsyncEngine:
    """Return the global async engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency – yields an async session, auto-closes."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager for use outside FastAPI request cycle."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables defined in the ORM metadata."""
    from server.db.models import Base  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Safely attempt to add new Deep Brain columns to existing trades table
        try:
            from sqlalchemy import text
            # Ignore errors if columns already exist
            await conn.execute(text("ALTER TABLE trades ADD COLUMN features_json TEXT"))
            await conn.execute(text("ALTER TABLE trades ADD COLUMN brain_prediction FLOAT"))
            await conn.execute(text("ALTER TABLE trades ADD COLUMN brain_reason TEXT"))
            await conn.execute(text("ALTER TABLE trades ADD COLUMN is_evaluated BOOLEAN DEFAULT FALSE"))
        except Exception as e:
            logger.debug(f"Columns might already exist or alter failed: {e}")
            
    logger.info("Database tables created / verified / altered.")


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed.")
