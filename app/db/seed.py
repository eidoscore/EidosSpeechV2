"""
eidosSpeech v2 — Database Initialization
Creates all tables on startup. Idempotent — safe to call multiple times.
"""

import logging
from app.db.database import engine, enable_wal_mode
from app.db.models import Base

logger = logging.getLogger(__name__)


async def init_db():
    """
    Initialize the database:
    1. Enable WAL mode
    2. Create all tables (idempotent via create_all)
    """
    logger.info("DB_INIT starting database initialization")

    # Enable WAL mode first
    await enable_wal_mode()

    # Create all tables (skip existing ones)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("DB_INIT all tables created successfully")
