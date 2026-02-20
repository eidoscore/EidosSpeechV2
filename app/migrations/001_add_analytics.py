"""
Migration 001: Add analytics tracking (PageView table)
"""
import asyncio
import logging
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def upgrade():
    """Add PageView table for analytics tracking"""
    async with AsyncSessionLocal() as session:
        try:
            # Check if table already exists
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='page_views'")
            )
            if result.fetchone():
                logger.info("Migration 001: PageView table already exists, skipping")
                return
            
            # Create PageView table
            await session.execute(text("""
                CREATE TABLE page_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path VARCHAR(500) NOT NULL,
                    ip_address VARCHAR(45),
                    country VARCHAR(2),
                    user_agent VARCHAR(500),
                    referrer VARCHAR(500),
                    date DATE NOT NULL,
                    timestamp TIMESTAMP NOT NULL
                )
            """))
            
            # Create indexes for better query performance
            await session.execute(text(
                "CREATE INDEX idx_page_views_date ON page_views(date)"
            ))
            await session.execute(text(
                "CREATE INDEX idx_page_views_path ON page_views(path)"
            ))
            await session.execute(text(
                "CREATE INDEX idx_page_views_country ON page_views(country)"
            ))
            
            await session.commit()
            logger.info("Migration 001: PageView table created successfully")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration 001 failed: {e}")
            raise

async def downgrade():
    """Remove PageView table"""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("DROP TABLE IF EXISTS page_views"))
            await session.commit()
            logger.info("Migration 001: PageView table dropped")
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration 001 downgrade failed: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(upgrade())
