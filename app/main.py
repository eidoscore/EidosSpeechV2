"""
eidosSpeech v2 — FastAPI Application
Main entry point: DB init, lifespan, CORS, page routes, cleanup tasks.
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__, __title__, __description__
from app.config import settings
from app.core.exceptions import EidosSpeechError, RateLimitError
from app.db.seed import init_db
from app.services.proxy_manager import init_proxy_manager, get_proxy_manager
from app.services.tts_engine import init_tts_engine

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


# ── Periodic Cleanup Task ──────────────────────────────────────────────────────
async def periodic_cleanup():
    """Run every 1 hour — batch-delete expired rows in a single transaction.
    
    SQLite locking strategy:
    - All 3 DELETEs run in ONE transaction → single write lock, shortest hold time
    - Staggered start (5 min after boot) so startup DB init completes first
    """
    await asyncio.sleep(300)  # Wait 5 min after startup before first run
    while True:
        try:
            from app.db.database import AsyncSessionLocal
            from app.db.models import TokenRevocation, RegistrationAttempt, User
            from sqlalchemy import delete

            async with AsyncSessionLocal() as db:
                now = datetime.now(timezone.utc)

                # Batch all deletes into ONE transaction — single write lock
                # 1. Expired JWT revocations
                r1 = await db.execute(
                    delete(TokenRevocation).where(TokenRevocation.expires_at < now)
                )
                # 2. Old registration attempt records (> 7 days)
                cutoff_7d = (now - timedelta(days=7)).date()
                r2 = await db.execute(
                    delete(RegistrationAttempt).where(RegistrationAttempt.date < cutoff_7d)
                )
                # 3. Unverified users older than 72 hours
                cutoff_72h = now - timedelta(hours=72)
                r3 = await db.execute(
                    delete(User).where(
                        User.is_verified == False,
                        User.created_at < cutoff_72h,
                    )
                )
                # 4. Old login attempts (> 30 days)
                from app.db.models import LoginAttempt
                cutoff_30d = now - timedelta(days=30)
                r4 = await db.execute(
                    delete(LoginAttempt).where(LoginAttempt.timestamp < cutoff_30d)
                )
                # 5. Old audit logs (> 90 days)
                from app.db.models import AuditLog
                cutoff_90d = now - timedelta(days=90)
                r5 = await db.execute(
                    delete(AuditLog).where(AuditLog.timestamp < cutoff_90d)
                )

                await db.commit()

                deleted = r1.rowcount + r2.rowcount + r3.rowcount + r4.rowcount + r5.rowcount
                if deleted > 0:
                    logger.info(
                        f"CLEANUP_COMPLETE revocations={r1.rowcount} "
                        f"reg_attempts={r2.rowcount} unverified_users={r3.rowcount} "
                        f"login_attempts={r4.rowcount} audit_logs={r5.rowcount}"
                    )

            # Non-DB cleanup (no lock needed)
            get_proxy_manager().reset_all()
            from app.core.rate_limiter import get_rate_limiter
            get_rate_limiter().cleanup_stale_entries()

        except Exception as e:
            logger.error(f"CLEANUP_ERROR error={e}")

        await asyncio.sleep(3600)  # Run every hour


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info(f"STARTUP eidosSpeech {__version__} starting...")

    # Create required directories
    Path("./data/db").mkdir(parents=True, exist_ok=True)
    Path("./data/cache").mkdir(parents=True, exist_ok=True)
    logger.info("STARTUP data directories created")

    # Startup validation (fails loudly if invalid config)
    try:
        settings.validate_startup()
    except SystemExit:
        logger.critical("STARTUP config validation failed — check environment variables")
        raise

    # Initialize database
    await init_db()
    logger.info("STARTUP database initialized")

    # Initialize proxy manager
    proxy_mgr = init_proxy_manager(settings.proxy_list)

    # Initialize TTS engine with proxy manager
    init_tts_engine(proxy_mgr)
    logger.info("STARTUP TTS engine ready")

    # Pre-load voice list
    try:
        from app.services.voice_service import get_all_voices
        voices = await get_all_voices()
        logger.info(f"STARTUP voice cache loaded voices={len(voices)}")
    except Exception as e:
        logger.warning(f"STARTUP voice preload failed (will retry on demand): {e}")

    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("STARTUP periodic cleanup task started")

    logger.info(f"STARTUP eidosSpeech {__version__} ready!")

    yield  # App is running

    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("SHUTDOWN eidosSpeech stopped")


# ── FastAPI App ────────────────────────────────────────────────────────────────
# Conditionally disable docs in production
docs_url = "/docs" if settings.debug else None
redoc_url = "/redoc" if settings.debug else None

app = FastAPI(
    title=__title__,
    description=__description__,
    version=__version__,
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=lifespan,
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"https://{settings.public_domain}",
        f"http://{settings.public_domain}",
        "http://localhost:8001",
        "http://localhost:3000",
        "http://127.0.0.1:8001",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Admin-Key"],
    expose_headers=[
        "X-RateLimit-Tier",
        "X-RateLimit-Limit-Day",
        "X-RateLimit-Remaining-Day",
        "X-RateLimit-Limit-Min",
        "X-RateLimit-Char-Limit",
        "X-Cache-Hit",
        "X-Cache-Key",
        "Retry-After",
    ],
)


# ── Security Headers Middleware ────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://challenges.cloudflare.com https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self' https://challenges.cloudflare.com; "
        "frame-src https://challenges.cloudflare.com; "
        "frame-ancestors 'none';"
    )
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # XSS protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    return response


# ── Request ID Middleware ──────────────────────────────────────────────────────
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID for tracing"""
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)

# ── Global Exception Handlers ──────────────────────────────────────────────────
@app.exception_handler(EidosSpeechError)
async def eidosspeech_error_handler(request: Request, exc: EidosSpeechError):
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=headers,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    # API routes return JSON, page routes return 404 page
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"error": "NotFoundError", "message": "Endpoint not found"},
        )
    # For page routes, redirect to landing
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/")


# ── SEO & Favicon Routes ──────────────────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon"""
    path = STATIC_DIR / "favicon.ico"
    if path.exists():
        return FileResponse(str(path), media_type="image/x-icon")
    return JSONResponse({}, status_code=404)


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Serve robots.txt for SEO"""
    path = STATIC_DIR / "robots.txt"
    if path.exists():
        return FileResponse(str(path), media_type="text/plain")
    return JSONResponse({}, status_code=404)


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    """Serve sitemap.xml for SEO"""
    path = STATIC_DIR / "sitemap.xml"
    if path.exists():
        return FileResponse(str(path), media_type="application/xml")
    return JSONResponse({}, status_code=404)


# ── API Routes ─────────────────────────────────────────────────────────────────
from app.api.v1 import router as api_v1_router
app.include_router(api_v1_router, prefix="/api/v1")

# ── Static Files ───────────────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Page Routes ───────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def landing_page():
    """Landing page"""
    path = STATIC_DIR / "landing.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"message": "eidosSpeech v2 API", "version": __version__})


@app.get("/app", include_in_schema=False)
async def app_page():
    """TTS App page"""
    path = STATIC_DIR / "index.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "App page not found"}, status_code=404)


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page():
    """User dashboard page"""
    path = STATIC_DIR / "dashboard.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Dashboard not found"}, status_code=404)


@app.get("/tos", include_in_schema=False)
async def tos_page():
    """Terms of Service"""
    path = STATIC_DIR / "tos.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "ToS page not found"}, status_code=404)


@app.get("/privacy", include_in_schema=False)
async def privacy_page():
    """Privacy Policy"""
    path = STATIC_DIR / "privacy.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Privacy page not found"}, status_code=404)


@app.get("/verify-email", include_in_schema=False)
async def verify_email_page():
    """Email verification page"""
    path = STATIC_DIR / "verify-email.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Page not found"}, status_code=404)


@app.get("/reset-password", include_in_schema=False)
async def reset_password_page():
    """Password reset page"""
    path = STATIC_DIR / "reset-password.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Page not found"}, status_code=404)


@app.get("/api-docs", include_in_schema=False)
async def api_docs_page():
    """Custom API documentation page"""
    path = STATIC_DIR / "api-docs.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "API docs not found"}, status_code=404)


@app.get("/admin", include_in_schema=False)
async def admin_page():
    """Admin panel page"""
    path = STATIC_DIR / "admin.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Admin page not found"}, status_code=404)
