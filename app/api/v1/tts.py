"""
eidosSpeech v2 — TTS Endpoint
POST /api/v1/tts — Generate text-to-speech audio.
Integrates: RequestContext, RateLimiter, Cache, ProxyManager.
"""

import hashlib
import json
import logging
import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.core.auth import resolve_request_context, RequestContext
from app.core.rate_limiter import get_rate_limiter, RateLimiter
from app.core.cache import get_cache
from app.core.exceptions import InternalError, ServiceUnavailableError
from app.db.database import get_db
from app.db.models import ApiKey
from app.models.schemas import TTSRequest
from app.services.tts_engine import get_tts_engine

router = APIRouter()
logger = logging.getLogger(__name__)


def compute_cache_key(req: TTSRequest) -> str:
    """
    Generate deterministic SHA256 hash for TTS request.
    Note: volume is excluded because edge-tts doesn't actually use it.
    Including it would cause unnecessary cache misses.
    """
    content = json.dumps({
        "text": req.text,
        "voice": req.voice,
        "rate": req.rate,
        "pitch": req.pitch,
        # volume excluded - edge-tts ignores this parameter
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


@router.post("/tts")
async def generate_tts(
    tts_request: TTSRequest,
    request: Request,
    ctx: RequestContext = Depends(resolve_request_context),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Generate TTS audio from text.
    Rate-limited by tier (anonymous: 5/day, 500ch; registered: 30/day, 1000ch).
    Returns MP3 audio file with X-RateLimit-* headers.
    """
    text = tts_request.text.strip()

    # ── 1. Rate limit check (char, per-min, per-day) ──────────
    usage = await rate_limiter.check_and_consume(ctx, db, len(text))

    # ── 2. Cache check ────────────────────────────────────────
    cache = get_cache()
    cache_key = compute_cache_key(tts_request)
    cached_path = cache.get(cache_key)

    rl_headers = rate_limiter.get_headers(ctx, usage)

    if cached_path:
        logger.info(f"TTS_CACHE_HIT key={cache_key[:8]}... tier={ctx.tier}")
        rl_headers["X-Cache-Hit"] = "true"
        rl_headers["X-Cache-Key"] = cache_key[:16]
        return FileResponse(
            path=cached_path,
            media_type="audio/mpeg",
            headers=rl_headers,
            filename="tts_audio.mp3",
        )

    # ── 3. Acquire concurrent semaphore ───────────────────────
    async with rate_limiter.acquire_concurrent(ctx):
        # ── 4. Generate via TTS engine ────────────────────────
        tts_engine = get_tts_engine()
        try:
            audio_bytes = await tts_engine.synthesize(
                text=text,
                voice=tts_request.voice,
                rate=tts_request.rate,
                pitch=tts_request.pitch,
                volume=tts_request.volume,
            )
        except RuntimeError as e:
            logger.error(f"TTS_ENGINE_ERROR voice={tts_request.voice} error={e}")
            raise ServiceUnavailableError(
                "TTS generation failed. The service may be temporarily unavailable."
            )

        # ── 5. Save to cache ──────────────────────────────────
        cached_path = cache.put(cache_key, audio_bytes)

        # ── 6. Update API key last_used_at ────────────────────
        if ctx.api_key_id:
            key = await db.get(ApiKey, ctx.api_key_id)
            if key:
                from datetime import datetime, timezone
                key.last_used_at = datetime.now(timezone.utc)
                await db.commit()

        # ── 7. Return with rate limit headers ─────────────────
        rl_headers["X-Cache-Hit"] = "false"
        rl_headers["X-Cache-Key"] = cache_key[:16]

        logger.info(
            f"TTS_GENERATED voice={tts_request.voice} "
            f"len={len(text)} tier={ctx.tier} "
            f"remaining_day={rl_headers.get('X-RateLimit-Remaining-Day')}"
        )

        return FileResponse(
            path=cached_path,
            media_type="audio/mpeg",
            headers=rl_headers,
            filename="tts_audio.mp3",
        )
