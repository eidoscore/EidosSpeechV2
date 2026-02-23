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
from app.core.rate_limiter import get_rate_limiter
from app.db.database import get_db
from app.services.proxy_manager import get_proxy_manager

router = APIRouter()

# Track startup time
_start_time = time.time()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    Returns: status (ok/degraded), version, db status, cache stats, proxy status, uptime, load metrics.
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
    
    # Load metrics (heavy operations)
    rate_limiter = get_rate_limiter()
    heavy_sem = rate_limiter._global_heavy_semaphore
    heavy_active = heavy_sem._value  # Available slots
    import os
    heavy_max = int(os.getenv("MAX_HEAVY_OPERATIONS", "20"))
    heavy_in_use = heavy_max - heavy_active

    uptime = time.time() - _start_time
    overall_status = "ok" if db_status == "ok" else "degraded"
    
    # Add warning if overloaded
    if heavy_in_use >= heavy_max * 0.9:  # 90% capacity
        overall_status = "degraded"

    return {
        "status": overall_status,
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db": db_status,
        "cache": cache_stats,
        "proxy": proxy_status,
        "uptime_seconds": round(uptime, 1),
        "load": {
            "heavy_operations_active": heavy_in_use,
            "heavy_operations_available": heavy_active,
            "heavy_operations_max": heavy_max,
            "heavy_operations_usage_pct": round((heavy_in_use / heavy_max) * 100, 1)
        }
    }
