"""
Migration script to add UUID column to users table
Run this ONCE after deploying the UUID changes
"""

import asyncio
import sqlite3
import uuid
from pathlib import Path


async def migrate_add_uuid():
    """Add UUID column to users table and generate UUIDs for existing users"""
    
    db_path = Path("data/db/eidosspeech.db")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    print(f"📦 Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if uuid column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'uuid' in columns:
            print("✅ UUID column already exists, skipping migration")
            return
        
        print("➕ Adding UUID column to users table...")
        
        # Add uuid column (nullable first)
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN uuid TEXT
        """)
        
        # Generate UUIDs for existing users
        cursor.execute("SELECT id FROM users")
        user_ids = cursor.fetchall()
        
        print(f"🔄 Generating UUIDs for {len(user_ids)} existing users...")
        
        for (user_id,) in user_ids:
            user_uuid = str(uuid.uuid4())
            cursor.execute(
                "UPDATE users SET uuid = ? WHERE id = ?",
                (user_uuid, user_id)
            )
        
        # Create unique index on uuid
        print("📇 Creating unique index on UUID column...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_uuid ON users(uuid)
        """)
        
        conn.commit()
        
        # Verify migration
        cursor.execute("SELECT COUNT(*) FROM users WHERE uuid IS NULL")
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"⚠️  Warning: {null_count} users still have NULL uuid")
        else:
            print("✅ Migration completed successfully!")
            print(f"   - Added UUID column")
            print(f"   - Generated UUIDs for {len(user_ids)} users")
            print(f"   - Created unique index")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("UUID Migration Script")
    print("=" * 60)
    asyncio.run(migrate_add_uuid())
    print("=" * 60)
