"""
eidosSpeech v2 — Health Check Endpoint
GET /api/v1/health — Returns service status including DB and proxy status.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app import __version__
from app.core.cache import get_cache
from app.db.database import get_db
from app.services.proxy_manager import get_proxy_manager

router = APIRouter()

# Track startup time
_start_time = time.time()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    Returns: status (ok/degraded), version, db status, cache stats, proxy status, uptime.
    """
    # DB connectivity check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {type(e).__name__}"

    # Cache stats
    cache = get_cache()
    cache_stats = cache.stats()

    # Proxy status
    proxy_mgr = get_proxy_manager()
    proxy_status = proxy_mgr.get_status()

    uptime = time.time() - _start_time
    overall_status = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall_status,
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db": db_status,
        "cache": cache_stats,
        "proxy": proxy_status,
        "uptime_seconds": round(uptime, 1),
    }
