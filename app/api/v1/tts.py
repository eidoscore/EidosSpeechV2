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
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.core.auth import resolve_request_context, RequestContext
from app.core.rate_limiter import get_rate_limiter, RateLimiter
from app.core.cache import get_cache
from app.core.exceptions import InternalError, ServiceUnavailableError, ForbiddenError
from app.db.database import get_db
from app.db.models import ApiKey
from app.models.schemas import TTSRequest, TTSSubtitleRequest, ScriptRequest
from app.services.tts_engine import get_tts_engine

router = APIRouter()
logger = logging.getLogger(__name__)


def compute_cache_key(req: TTSRequest) -> str:
    """
    Generate deterministic SHA256 hash for TTS request.
    Note: volume is excluded because edge-tts doesn't actually use it.
    Including it would cause unnecessary cache misses.
    """
    data = {
        "text": req.text,
        "voice": req.voice,
        "rate": req.rate,
        "pitch": req.pitch,
        # volume excluded - edge-tts ignores this parameter
    }
    
    # Include style parameters if present
    if req.style:
        data["style"] = req.style
    if req.style_degree:
        data["style_degree"] = req.style_degree
    
    content = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
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
    request_type = "api_tts" if not ctx.is_web_ui else "webui_tts"
    usage = await rate_limiter.check_and_consume(ctx, db, len(text), request_type=request_type)

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
                style=tts_request.style,
                style_degree=tts_request.style_degree,
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



@router.post("/tts/subtitle")
async def generate_tts_with_subtitle(
    tts_request: TTSSubtitleRequest,
    request: Request,
    ctx: RequestContext = Depends(resolve_request_context),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Generate TTS audio + SRT subtitle file.
    Returns JSON with SRT content and cache key.
    Audio can be retrieved via normal /tts endpoint with same parameters.
    """
    text = tts_request.text.strip()

    # ── 1. Rate limit check ───────────────────────────────────
    request_type = "api_tts" if not ctx.is_web_ui else "webui_tts"
    usage = await rate_limiter.check_and_consume(ctx, db, len(text), request_type=request_type)

    # ── 2. Cache check (audio only, SRT always regenerated) ──
    cache = get_cache()
    cache_key = compute_cache_key(tts_request)

    # ── 3. Acquire concurrent semaphore ───────────────────────
    async with rate_limiter.acquire_concurrent(ctx):
        # ── 4. Generate via TTS engine with subtitles ─────────
        tts_engine = get_tts_engine()
        try:
            audio_bytes, srt_content = await tts_engine.synthesize_with_subtitles(
                text=text,
                voice=tts_request.voice,
                rate=tts_request.rate,
                pitch=tts_request.pitch,
                volume=tts_request.volume,
                words_per_cue=tts_request.words_per_cue,
                style=tts_request.style if hasattr(tts_request, 'style') else None,
                style_degree=tts_request.style_degree if hasattr(tts_request, 'style_degree') else None,
            )
        except RuntimeError as e:
            logger.error(f"TTS_SRT_ENGINE_ERROR voice={tts_request.voice} error={e}")
            raise ServiceUnavailableError(
                "TTS+SRT generation failed. The service may be temporarily unavailable."
            )

        # ── 5. Save audio to cache ────────────────────────────
        cached_path = cache.put(cache_key, audio_bytes)

        # ── 6. Update API key last_used_at ────────────────────
        if ctx.api_key_id:
            key = await db.get(ApiKey, ctx.api_key_id)
            if key:
                from datetime import datetime, timezone
                key.last_used_at = datetime.now(timezone.utc)
                await db.commit()

        # ── 7. Return JSON with SRT + headers ─────────────────
        rl_headers = rate_limiter.get_headers(ctx, usage)
        rl_headers["X-Cache-Hit"] = "false"
        rl_headers["X-Cache-Key"] = cache_key[:16]

        logger.info(
            f"TTS_SRT_GENERATED voice={tts_request.voice} "
            f"len={len(text)} tier={ctx.tier} words_per_cue={tts_request.words_per_cue}"
        )

        return JSONResponse(
            content={
                "srt": srt_content,
                "cache_key": cache_key[:16],
                "cache_hit": False,
            },
            headers=rl_headers,
        )



@router.post("/tts/script")
async def generate_script(
    script_request: ScriptRequest,
    request: Request,
    ctx: RequestContext = Depends(resolve_request_context),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Generate multi-voice script audio (dialog/podcast).
    Script format: [Speaker] text
    Each line costs characters toward rate limit.
    
    IMPORTANT: Multi-voice is ONLY available for registered users.
    """
    from app.services.script_service import parse_script, generate_script_audio
    
    # ── 0. Block anonymous users ──────────────────────────────
    if ctx.tier == "anonymous":
        raise RateLimitError(
            "Multi-voice script is only available for registered users. "
            "Please sign up to access this feature.",
            retry_after=0,
            detail={"feature": "multi-voice", "tier_required": "registered"}
        )
    
    # ── 0.1. Block unverified users ───────────────────────────
    if not ctx.is_verified:
        raise ForbiddenError(
            "Please verify your email address to use multi-voice features. "
            "Check your inbox for the verification link or request a new one from your dashboard."
        )
    
    # ── 1. Parse script ────────────────────────────────────────
    try:
        lines = parse_script(script_request.script)
    except ValueError as e:
        raise InternalError(f"Script parsing failed: {e}")
    
    # ── 2. Calculate total characters ─────────────────────────
    total_chars = sum(len(line.text) for line in lines)
    
    # ── 3. Rate limit check ───────────────────────────────────
    request_type = "api_multivoice" if not ctx.is_web_ui else "webui_multivoice"
    usage = await rate_limiter.check_and_consume(ctx, db, total_chars, request_type=request_type)
    
    # ── 4. Acquire concurrent semaphore (per-user) ───────────
    async with rate_limiter.acquire_concurrent(ctx):
        # ── 5. Acquire heavy operation slot (global limit) ───
        async with rate_limiter.acquire_heavy_operation():
            # ── 6. Generate multi-voice audio ─────────────────
            try:
                audio_bytes = await generate_script_audio(
                    lines=lines,
                    voice_map=script_request.voice_map,
                    pause_ms=script_request.pause_ms,
                    rate=script_request.rate,
                    pitch=script_request.pitch,
                    volume=script_request.volume,
                )
            except RuntimeError as e:
                logger.error(f"SCRIPT_ENGINE_ERROR lines={len(lines)} error={e}")
                raise ServiceUnavailableError(
                    f"Script generation failed: {e}"
                )
        
        # ── 7. Update API key last_used_at ────────────────────
        if ctx.api_key_id:
            key = await db.get(ApiKey, ctx.api_key_id)
            if key:
                from datetime import datetime, timezone
                key.last_used_at = datetime.now(timezone.utc)
                await db.commit()
        
        # ── 8. Return audio with rate limit headers ───────────
        rl_headers = rate_limiter.get_headers(ctx, usage)
        
        logger.info(
            f"SCRIPT_GENERATED lines={len(lines)} "
            f"chars={total_chars} tier={ctx.tier} "
            f"size={len(audio_bytes)} bytes"
        )
        
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers=rl_headers,
        )
