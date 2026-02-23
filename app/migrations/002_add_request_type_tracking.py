"""
Migration 002: Add request type tracking to DailyUsage
Adds columns to track different types of TTS requests for detailed analytics.
"""

from sqlalchemy import text


async def upgrade(db):
    """Add request type tracking columns"""
    
    # Add new columns for request type breakdown
    await db.execute(text("""
        ALTER TABLE daily_usage 
        ADD COLUMN webui_tts_count INTEGER DEFAULT 0 NOT NULL
    """))
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        ADD COLUMN api_tts_count INTEGER DEFAULT 0 NOT NULL
    """))
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        ADD COLUMN webui_multivoice_count INTEGER DEFAULT 0 NOT NULL
    """))
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        ADD COLUMN api_multivoice_count INTEGER DEFAULT 0 NOT NULL
    """))
    
    # Migrate existing data: assume all existing requests are webui_tts
    await db.execute(text("""
        UPDATE daily_usage 
        SET webui_tts_count = request_count 
        WHERE webui_tts_count = 0
    """))
    
    await db.commit()
    print("✓ Migration 002: Added request type tracking columns")


async def downgrade(db):
    """Remove request type tracking columns"""
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        DROP COLUMN webui_tts_count
    """))
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        DROP COLUMN api_tts_count
    """))
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        DROP COLUMN webui_multivoice_count
    """))
    
    await db.execute(text("""
        ALTER TABLE daily_usage 
        DROP COLUMN api_multivoice_count
    """))
    
    await db.commit()
    print("✓ Migration 002: Removed request type tracking columns")
