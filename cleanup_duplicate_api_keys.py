#!/usr/bin/env python3
"""
Cleanup script for duplicate active API keys.
This script deactivates all but the most recent active API key for each user.
"""
import asyncio
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session_maker
from app.db.models import ApiKey, User


async def cleanup_duplicate_keys():
    """Find and deactivate duplicate active API keys, keeping only the most recent one per user."""
    async with async_session_maker() as db:
        # Find users with multiple active keys
        result = await db.execute(
            select(ApiKey.user_id, func.count(ApiKey.id).label('key_count'))
            .where(ApiKey.is_active == True)
            .group_by(ApiKey.user_id)
            .having(func.count(ApiKey.id) > 1)
        )
        
        users_with_dupes = result.all()
        
        if not users_with_dupes:
            print("✅ No duplicate active API keys found!")
            return
        
        print(f"⚠️  Found {len(users_with_dupes)} users with multiple active API keys")
        
        total_deactivated = 0
        
        for user_id, key_count in users_with_dupes:
            # Get user email for logging
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            user_email = user.email if user else f"user_id:{user_id}"
            
            print(f"\n👤 User: {user_email}")
            print(f"   Found {key_count} active keys")
            
            # Get all active keys for this user, ordered by creation date (newest first)
            keys_result = await db.execute(
                select(ApiKey)
                .where(ApiKey.user_id == user_id, ApiKey.is_active == True)
                .order_by(desc(ApiKey.created_at))
            )
            keys = keys_result.scalars().all()
            
            # Keep the first (newest) key, deactivate the rest
            for i, key in enumerate(keys):
                if i == 0:
                    print(f"   ✅ Keeping: {key.key[:12]}... (created: {key.created_at})")
                else:
                    print(f"   ❌ Deactivating: {key.key[:12]}... (created: {key.created_at})")
                    key.is_active = False
                    total_deactivated += 1
        
        # Commit all changes
        await db.commit()
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Deactivated {total_deactivated} duplicate API keys")
        print(f"   {len(users_with_dupes)} users now have exactly 1 active key")


async def verify_cleanup():
    """Verify that no users have multiple active keys."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(ApiKey.user_id, func.count(ApiKey.id).label('key_count'))
            .where(ApiKey.is_active == True)
            .group_by(ApiKey.user_id)
            .having(func.count(ApiKey.id) > 1)
        )
        
        dupes = result.all()
        
        if dupes:
            print(f"❌ Verification failed! Still found {len(dupes)} users with multiple active keys")
            return False
        else:
            print("✅ Verification passed! All users have at most 1 active API key")
            return True


async def main():
    print("=" * 60)
    print("API Key Cleanup Script")
    print("=" * 60)
    print()
    
    await cleanup_duplicate_keys()
    print()
    print("=" * 60)
    print("Verifying cleanup...")
    print("=" * 60)
    print()
    await verify_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
