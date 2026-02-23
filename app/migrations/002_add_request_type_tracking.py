"""
Migration 002: Add request type tracking to DailyUsage
Adds columns to track different types of TTS requests for detailed analytics.
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def upgrade():
    """Add request type tracking columns"""
    async with AsyncSessionLocal() as session:
        try:
            # Check if columns already exist
            result = await session.execute(
                text("PRAGMA table_info(daily_usage)")
            )
            columns = [row[1] for row in result.fetchall()]
            
            if 'webui_tts_count' in columns:
                logger.info("Migration 002: Request type columns already exist, skipping")
                return
            
            # Add new columns for request type breakdown
            await session.execute(text("""
                ALTER TABLE daily_usage 
                ADD COLUMN webui_tts_count INTEGER DEFAULT 0 NOT NULL
            """))
            
            await session.execute(text("""
                ALTER TABLE daily_usage 
                ADD COLUMN api_tts_count INTEGER DEFAULT 0 NOT NULL
            """))
            
            await session.execute(text("""
                ALTER TABLE daily_usage 
                ADD COLUMN webui_multivoice_count INTEGER DEFAULT 0 NOT NULL
            """))
            
            await session.execute(text("""
                ALTER TABLE daily_usage 
                ADD COLUMN api_multivoice_count INTEGER DEFAULT 0 NOT NULL
            """))
            
            # Migrate existing data: assume all existing requests are webui_tts
            await session.execute(text("""
                UPDATE daily_usage 
                SET webui_tts_count = request_count 
                WHERE webui_tts_count = 0
            """))
            
            await session.commit()
            logger.info("Migration 002: Added request type tracking columns")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration 002 failed: {e}")
            raise


async def downgrade():
    """Remove request type tracking columns"""
    async with AsyncSessionLocal() as session:
        try:
            # SQLite doesn't support DROP COLUMN directly
            # Would need to recreate table, so just log warning
            logger.warning("Migration 002 downgrade: SQLite doesn't support DROP COLUMN")
            logger.warning("Manual intervention required to remove columns")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration 002 downgrade failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(upgrade())
