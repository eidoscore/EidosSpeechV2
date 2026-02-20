#!/usr/bin/env python3
"""
Database Migration Script
Run this to create new tables (login_attempts, audit_logs)
"""

import asyncio
import sys
from app.db.seed import init_db

async def main():
    print("🔄 Starting database migration...")
    print("📋 Creating new tables: login_attempts, audit_logs")
    
    try:
        await init_db()
        print("✅ Migration completed successfully!")
        print("📊 Tables created:")
        print("   - login_attempts (for brute-force detection)")
        print("   - audit_logs (for security event tracking)")
        return 0
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
