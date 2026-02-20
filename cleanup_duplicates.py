#!/usr/bin/env python3
"""
Cleanup duplicate DailyUsage rows in database.
Run this once to fix data corruption.
"""
import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import AsyncSessionLocal
from app.db.models import DailyUsage
from sqlalchemy import select, delete


async def cleanup_duplicates():
    """Remove duplicate DailyUsage rows, keeping only the one with highest request_count"""
    async with AsyncSessionLocal() as db:
        # Find all DailyUsage rows
        result = await db.execute(select(DailyUsage))
        all_usage = result.scalars().all()
        
        # Group by (api_key_id, date) or (ip_address, date)
        groups = {}
        for usage in all_usage:
            if usage.api_key_id:
                key = (usage.api_key_id, usage.date)
            else:
                key = (usage.ip_address, usage.date)
            
            if key not in groups:
                groups[key] = []
            groups[key].append(usage)
        
        # Find duplicates
        duplicates_found = 0
        rows_deleted = 0
        
        for key, usages in groups.items():
            if len(usages) > 1:
                duplicates_found += 1
                # Sort by request_count desc, keep the highest
                usages.sort(key=lambda u: u.request_count, reverse=True)
                keep = usages[0]
                delete_ids = [u.id for u in usages[1:]]
                
                print(f"Duplicate found for {key}: keeping id={keep.id} (requests={keep.request_count}), deleting {len(delete_ids)} rows")
                
                # Delete duplicates
                await db.execute(
                    delete(DailyUsage).where(DailyUsage.id.in_(delete_ids))
                )
                rows_deleted += len(delete_ids)
        
        await db.commit()
        
        print(f"\nCleanup complete:")
        print(f"  Duplicate groups found: {duplicates_found}")
        print(f"  Rows deleted: {rows_deleted}")
        print(f"  Total unique usage records: {len(groups)}")


if __name__ == "__main__":
    print("Starting DailyUsage duplicate cleanup...")
    asyncio.run(cleanup_duplicates())
    print("Done!")
