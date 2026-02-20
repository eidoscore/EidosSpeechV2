"""
Auto-run all database migrations on startup
"""
import asyncio
import importlib
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

async def run_migrations():
    """Run all migration files in order"""
    migrations_dir = Path(__file__).parent / "app" / "migrations"
    
    # Get all migration files (001_*.py, 002_*.py, etc.)
    migration_files = sorted([
        f for f in migrations_dir.glob("[0-9][0-9][0-9]_*.py")
        if f.name != "__init__.py"
    ])
    
    if not migration_files:
        logger.info("No migrations found")
        return
    
    logger.info(f"Found {len(migration_files)} migration(s)")
    
    for migration_file in migration_files:
        migration_name = migration_file.stem
        logger.info(f"Running migration: {migration_name}")
        
        try:
            # Import migration module
            module_path = f"app.migrations.{migration_name}"
            migration_module = importlib.import_module(module_path)
            
            # Run upgrade function
            if hasattr(migration_module, "upgrade"):
                await migration_module.upgrade()
                logger.info(f"✓ Migration {migration_name} completed")
            else:
                logger.warning(f"Migration {migration_name} has no upgrade() function")
                
        except Exception as e:
            logger.error(f"✗ Migration {migration_name} failed: {e}")
            # Continue with other migrations instead of failing completely
            continue
    
    logger.info("All migrations completed")

if __name__ == "__main__":
    try:
        asyncio.run(run_migrations())
    except Exception as e:
        logger.error(f"Migration runner failed: {e}")
        sys.exit(1)
