#!/usr/bin/env python3
"""
Migration: Add page_views table for analytics tracking
Run this after deploying the new code
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import engine
from app.db.models import Base, PageView


async def migrate():
    """Create page_views table"""
    print("🔄 Creating page_views table...")
    
    async with engine.begin() as conn:
        # Create only the PageView table
        await conn.run_sync(PageView.__table__.create, checkfirst=True)
    
    print("✅ Migration complete! page_views table created.")
    print("\n📊 Analytics tracking is now active.")
    print("   - Page views will be tracked automatically")
    print("   - GeoIP lookup via ipapi.co (free tier)")
    print("   - View analytics in Admin Dashboard → Analytics tab")


if __name__ == "__main__":
    asyncio.run(migrate())
