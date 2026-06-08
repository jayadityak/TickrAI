"""Async Postgres connection pool.

Uses asyncpg with a lazy connection pool. Falls back gracefully if
DATABASE_URL is not configured (development without a DB).

Usage:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(...)
"""

import logging

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_pool_init_failed = False  # Don't retry after a fatal init error


async def get_pool() -> asyncpg.Pool | None:
    """Return the shared connection pool, initialising it on first call.

    Returns None if DATABASE_URL is not set or connection failed.
    """
    global _pool, _pool_init_failed

    if _pool is not None:
        return _pool

    if _pool_init_failed:
        return None

    if not settings.database_url:
        return None

    try:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
            statement_cache_size=0,   # Required for PgBouncer / Railway proxy
        )
        await _ensure_schema(_pool)
        logger.info("DB: connection pool created")
    except Exception as e:
        logger.warning("DB: failed to connect — %s", e)
        _pool_init_failed = True
        _pool = None

    return _pool


async def _ensure_schema(pool: asyncpg.Pool) -> None:
    """Create the users table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                email       TEXT NOT NULL,
                name        TEXT,
                picture     TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                last_login  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    logger.info("DB: schema ready")
