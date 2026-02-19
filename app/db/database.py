"""
eidosSpeech v2 — SQLite Async Database Engine (Optimized)

SQLite-specific optimizations:
- WAL mode: concurrent reads, single writer — avoids reader/writer locking
- PRAGMA busy_timeout: wait instead of immediately failing on locked DB
- PRAGMA cache_size: larger page cache reduces disk I/O
- PRAGMA temp_store=MEMORY: temp tables in RAM
- PRAGMA mmap_size: memory-mapped I/O for read performance
- Pool size = 1: SQLite does NOT benefit from connection pool > 1
  (multiple connections = locking contention, WAL handles concurrency)
- NullPool disabled: using StaticPool in tests, SingletonThreadPool in prod
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from sqlalchemy.pool import StaticPool
from app.config import settings

logger = logging.getLogger(__name__)

_is_sqlite = settings.database_url.startswith("sqlite")

# ── Engine ─────────────────────────────────────────────────────────────────────
# SQLite: pool_size is irrelevant (uses SingletonThreadPool), but we MUST set
# check_same_thread=False for asyncio + aiosqlite.
# Do NOT use pool_size / max_overflow args — SQLite doesn't support them.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={
        "check_same_thread": False,  # Required for aiosqlite
        "timeout": 30,               # Seconds to wait if DB is locked (busy_timeout via SQLAlchemy)
    },
    # For SQLite: keep a single connection in the pool.
    # Multiple connections to SQLite cause locking — WAL handles concurrency at OS level.
    poolclass=StaticPool if ":memory:" in settings.database_url else None,
)

# ── Session Factory ────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire after commit (prevents extra SELECT)
    autoflush=False,         # Manual flush control — avoids implicit writes mid-transaction
    autocommit=False,
)


# ── FastAPI Dependency ─────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency — yields scoped DB session per request.
    Rollback on exception, always close on exit.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── SQLite PRAGMA Tuning ───────────────────────────────────────────────────────
async def enable_wal_mode():
    """
    Apply SQLite performance PRAGMAs on startup.

    WAL (Write-Ahead Logging):
    - Readers do NOT block writers, writers do NOT block readers
    - Multiple concurrent reads while one write is happening = fine
    - WAL file is checkpointed periodically (auto)

    busy_timeout = 5000ms:
    - If DB is briefly locked (another writer mid-commit), SQLite waits
      up to 5s before returning SQLITE_BUSY — prevents spurious lock errors
      under concurrent load (multiple gunicorn workers, async tasks)

    cache_size = -32000 (32 MB):
    - Larger page cache → fewer disk reads for hot data (users, api_keys)
    - Negative value = kilobytes (SQLite default is only 2 MB)

    mmap_size = 256 MB:
    - Memory-mapped I/O for reads — avoids syscall overhead on Linux

    temp_store = MEMORY:
    - Temporary tables (ORDER BY, GROUP BY intermediate results) stay in RAM

    synchronous = NORMAL:
    - Safe with WAL mode (WAL already protects against corruption)
    - Faster than FULL (default) — no fsync after every write

    foreign_keys = ON:
    - Enforce referential integrity (cascade deletes work correctly)
    """
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.execute(text("PRAGMA cache_size=-32000"))       # 32 MB page cache
        await conn.execute(text("PRAGMA temp_store=MEMORY"))
        await conn.execute(text("PRAGMA mmap_size=268435456"))     # 256 MB mmap
        await conn.execute(text("PRAGMA wal_autocheckpoint=1000")) # Checkpoint after 1000 pages

        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        logger.info(f"DB_INIT journal_mode={mode} — SQLite PRAGMAs applied")
