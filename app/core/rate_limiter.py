"""
eidosSpeech v2 — Hybrid Rate Limiter
Per-minute: in-memory sliding window (deque of timestamps)
Per-day: SQLite daily_usage table
Concurrent: asyncio.Semaphore(1) per identity — reject (not queue)
"""

import asyncio
import logging
import time
from collections import deque
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.auth import RequestContext
from app.core.exceptions import RateLimitError

logger = logging.getLogger(__name__)


def seconds_until_midnight_utc() -> int:
    """Seconds until next UTC midnight (daily rate limit reset)"""
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


class RateLimiter:
    """
    Hybrid rate limiter:
    - Per-minute: in-memory sliding window per identity
    - Per-day: SQLite daily_usage table
    - Concurrent: asyncio.Semaphore(1) per identity — reject if locked
    - Global concurrent: Semaphore(10) for heavy operations (script mode)
    """

    def __init__(self):
        # Per-minute: in-memory
        self._minute_windows: dict[str, deque] = {}
        # Concurrent: per-identity semaphore
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        # Global concurrent limit for heavy operations (script mode)
        # Configurable via environment variable for easy scaling
        import os
        max_heavy = int(os.getenv("MAX_HEAVY_OPERATIONS", "20"))  # Default 20
        self._global_heavy_semaphore = asyncio.Semaphore(max_heavy)
        # Lock for dict manipulation
        self._lock = asyncio.Lock()
        
        logger.info(f"RATE_LIMITER_INIT max_heavy_operations={max_heavy}")

    def _get_identity(self, ctx: RequestContext) -> str:
        """IP for anonymous, API key ID for registered"""
        if ctx.tier == "anonymous":
            return f"ip:{ctx.ip_address}"
        return f"key:{ctx.api_key_id}"

    async def check_and_consume(
        self,
        ctx: RequestContext,
        db: AsyncSession,
        text_len: int,
        request_type: str = "webui_tts",  # webui_tts, api_tts, webui_multivoice, api_multivoice
    ) -> "DailyUsageRow":
        """
        Check all rate limits and consume quota.
        Raises RateLimitError if any limit exceeded.
        On success: increments counters and returns usage row.
        """
        from app.db.models import DailyUsage
        identity = self._get_identity(ctx)

        # ── 1. Character limit ────────────────────────────────
        if text_len > ctx.char_limit:
            raise RateLimitError(
                f"Text too long. Max {ctx.char_limit} characters for {ctx.tier} tier. "
                f"Register for higher limits.",
                retry_after=0,
                detail={"char_limit": ctx.char_limit, "text_len": text_len, "tier": ctx.tier}
            )

        # ── 2. Per-minute limit (in-memory sliding window) ────
        now = time.monotonic()
        async with self._lock:
            if identity not in self._minute_windows:
                self._minute_windows[identity] = deque()
            window = self._minute_windows[identity]

        # Remove entries older than 60 seconds
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= ctx.req_per_min:
            oldest = window[0]
            retry_after = max(1, int(60 - (now - oldest)) + 1)
            logger.warning(f"RATE_LIMIT_MIN tier={ctx.tier} identity={identity}")
            raise RateLimitError(
                f"Per-minute limit exceeded ({ctx.req_per_min}/min for {ctx.tier} tier). "
                "Wait a moment and try again.",
                retry_after=retry_after,
                detail={"limit": ctx.req_per_min, "tier": ctx.tier, "window": "1min"}
            )

        # ── 3. Per-day limit (SQLite) ─────────────────────────
        today = date.today()  # UTC date
        usage = await self._get_or_create_usage(db, ctx, today)

        if usage.request_count >= ctx.req_per_day:
            retry_after = seconds_until_midnight_utc()
            logger.warning(f"RATE_LIMIT_DAY tier={ctx.tier} identity={identity}")
            raise RateLimitError(
                f"Daily limit reached ({ctx.req_per_day} requests/day for {ctx.tier} tier). "
                "Resets at UTC midnight.",
                retry_after=retry_after,
                detail={
                    "limit": ctx.req_per_day,
                    "used": usage.request_count,
                    "tier": ctx.tier,
                    "reset_at": "UTC midnight"
                }
            )

        # All checks passed — consume quota
        window.append(now)
        usage.request_count += 1
        usage.chars_used += text_len
        
        # Track request type for detailed analytics
        if request_type == "webui_tts":
            usage.webui_tts_count += 1
        elif request_type == "api_tts":
            usage.api_tts_count += 1
        elif request_type == "webui_multivoice":
            usage.webui_multivoice_count += 1
        elif request_type == "api_multivoice":
            usage.api_multivoice_count += 1
        
        await db.commit()

        return usage

    async def _get_or_create_usage(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        today: date,
    ):
        """
        Get or create daily usage row — SQLite-safe upsert pattern.

        Problem with naive SELECT → INSERT:
          Two concurrent requests (async tasks) could both see no row,
          then both try INSERT → IntegrityError or duplicate row.

        Solution: INSERT OR IGNORE (SQLite dialect) + re-SELECT.
        This is atomic at the SQLite level — no race possible.
        """
        from app.db.models import DailyUsage

        if ctx.tier == "registered" and ctx.api_key_id:
            where_clause = (
                DailyUsage.api_key_id == ctx.api_key_id,
                DailyUsage.date == today,
            )
            insert_values = dict(
                api_key_id=ctx.api_key_id,
                ip_address=None,
                date=today,
                request_count=0,
                chars_used=0,
            )
        else:
            where_clause = (
                DailyUsage.ip_address == ctx.ip_address,
                DailyUsage.api_key_id == None,
                DailyUsage.date == today,
            )
            insert_values = dict(
                api_key_id=None,
                ip_address=ctx.ip_address,
                date=today,
                request_count=0,
                chars_used=0,
            )

        # INSERT OR IGNORE: atomic, no duplicate rows, no race condition
        stmt = sqlite_insert(DailyUsage).values(**insert_values).prefix_with("OR IGNORE")
        await db.execute(stmt)
        # No commit here — we're in the same transaction; flush ensures row exists
        await db.flush()

        # Now SELECT the definitive row (always exists after above)
        # Use scalars().first() to handle potential duplicates gracefully
        result = await db.execute(
            select(DailyUsage).where(*where_clause)
        )
        usage = result.scalars().first()
        
        if not usage:
            # Fallback: create if somehow missing
            usage = DailyUsage(**insert_values)
            db.add(usage)
            await db.flush()
        
        return usage

    def get_headers(self, ctx: RequestContext, usage) -> dict:
        """Generate X-RateLimit-* response headers"""
        remaining = max(0, ctx.req_per_day - usage.request_count)
        return {
            "X-RateLimit-Tier": ctx.tier,
            "X-RateLimit-Limit-Day": str(ctx.req_per_day),
            "X-RateLimit-Remaining-Day": str(remaining),
            "X-RateLimit-Limit-Min": str(ctx.req_per_min),
            "X-RateLimit-Char-Limit": str(ctx.char_limit),
        }

    def acquire_concurrent(self, ctx: RequestContext):
        """
        Async context manager for concurrent request limit.
        Rejects (429) if another request is already processing for this identity.
        """
        return _ConcurrentGuard(self, ctx)

    def acquire_heavy_operation(self):
        """
        Async context manager for heavy operations (multi-voice script).
        Global limit of MAX_HEAVY_OPERATIONS concurrent operations across all users.
        Queues requests instead of rejecting (with timeout).
        """
        return _HeavyOperationGuard(self)

    def cleanup_stale_entries(self):
        """Remove stale in-memory entries (called by periodic cleanup)"""
        now = time.monotonic()
        cutoff = now - 300  # older than 5 minutes
        stale = [k for k, v in self._minute_windows.items()
                 if not v or v[-1] < cutoff]
        for k in stale:
            del self._minute_windows[k]
        if stale:
            logger.debug(f"RATE_LIMIT_CLEANUP removed={len(stale)} stale entries")


class _ConcurrentGuard:
    """Context manager that acquires a per-identity semaphore (reject if locked)"""

    def __init__(self, limiter: RateLimiter, ctx: RequestContext):
        self._limiter = limiter
        self._ctx = ctx
        self._identity = limiter._get_identity(ctx)
        self._sem = None

    async def __aenter__(self):
        identity = self._identity
        limiter = self._limiter

        async with limiter._lock:
            if identity not in limiter._semaphores:
                limiter._semaphores[identity] = asyncio.Semaphore(1)
            self._sem = limiter._semaphores[identity]

        if self._sem.locked():
            raise RateLimitError(
                "A request is already being processed. Please wait and try again.",
                retry_after=30,
                detail={"type": "concurrent_limit"}
            )
        await self._sem.acquire()
        return self

    async def __aexit__(self, *args):
        if self._sem:
            self._sem.release()


# Singleton instance
_rate_limiter: RateLimiter = None


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency — singleton rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


class _HeavyOperationGuard:
    """Context manager for global heavy operation limit"""

    def __init__(self, limiter: RateLimiter):
        self._limiter = limiter
        self._acquired = False

    async def __aenter__(self):
        try:
            # Wait up to 30 seconds for slot
            await asyncio.wait_for(
                self._limiter._global_heavy_semaphore.acquire(),
                timeout=30.0
            )
            self._acquired = True
            return self
        except asyncio.TimeoutError:
            raise RateLimitError(
                "Server is currently processing too many heavy requests. Please try again in a moment.",
                retry_after=30,
                detail={"type": "heavy_operation_limit"}
            )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._acquired:
            self._limiter._global_heavy_semaphore.release()
