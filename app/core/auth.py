"""
eidosSpeech v2 — Request Context Resolution + Auth
Replaces simple API key check with full tier detection:
  1. X-API-Key header → registered
  2. Authorization: Bearer <jwt> → registered
  3. No auth + own origin → anonymous (Web UI)
  4. No auth + external origin → 403
"""

import logging
from dataclasses import dataclass
from typing import Literal

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.exceptions import ForbiddenError, AuthenticationError
from app.core.jwt_handler import decode_token

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """
    Resolved request context — tier, identity, limits.
    Injected into TTS endpoint via Depends(resolve_request_context).
    """
    tier: Literal["anonymous", "registered"]
    api_key: str | None
    api_key_id: int | None
    user_id: int | None
    user_email: str | None
    is_verified: bool
    ip_address: str
    char_limit: int
    req_per_day: int
    req_per_min: int
    is_web_ui: bool


def get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For (nginx proxy)"""
    # Trust X-Real-IP from nginx
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]
    # X-Forwarded-For: first IP in chain
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    # Direct connection
    return request.client.host if request.client else "unknown"


def is_own_origin(request: Request) -> bool:
    """Check if request comes from our own domain (Web UI)"""
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    allowed = [
        f"https://{settings.public_domain}",
        f"http://{settings.public_domain}",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ]

    return any(
        origin.startswith(a) or referer.startswith(a)
        for a in allowed
    )


async def is_blacklisted(db: AsyncSession, ip: str, email: str = None) -> bool:
    """Check if IP or email is in blacklist table"""
    from app.db.models import Blacklist

    conditions = [Blacklist.value == ip, Blacklist.type == "ip"]
    result = await db.execute(
        select(Blacklist).where(Blacklist.type == "ip", Blacklist.value == ip)
    )
    if result.scalar_one_or_none():
        return True

    if email:
        result = await db.execute(
            select(Blacklist).where(Blacklist.type == "email", Blacklist.value == email)
        )
        if result.scalar_one_or_none():
            return True

    return False


from app.db.database import get_db
from fastapi import Depends

async def resolve_request_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RequestContext:
    """
    Determine request tier and limits.

    Resolution order:
    1. X-API-Key header → DB lookup → "registered" (API limits: 1000 char)
    2. Authorization: Bearer <jwt> → decode → load user's API key → "registered" (Web UI limits: 2000 char)
    3. No credentials + Origin = own domain → "anonymous" (Web UI: 500 char)
    4. No credentials + external Origin → 403 Forbidden
    """
    from app.db.models import ApiKey, User

    ip = get_client_ip(request)

    # Check IP blacklist first
    if await is_blacklisted(db, ip=ip):
        logger.warning(f"BLACKLIST_BLOCK ip={ip}")
        raise ForbiddenError("Access denied")

    # ── 1. X-API-Key header (External API call) ───────────────
    api_key_header = request.headers.get("x-api-key")
    if api_key_header:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.key == api_key_header,
                ApiKey.is_active == True
            )
        )
        key = result.scalar_one_or_none()

        if not key:
            raise ForbiddenError("Invalid or inactive API key")

        user = await db.get(User, key.user_id)
        if not user or not user.is_active:
            raise ForbiddenError("Account disabled or banned")

        # Check email blacklist
        if await is_blacklisted(db, ip=ip, email=user.email):
            raise ForbiddenError("Access denied")

        logger.debug(f"AUTH_API_KEY user_id={user.id} verified={user.is_verified} ip={ip}")
        return RequestContext(
            tier="registered",
            api_key=key.key,
            api_key_id=key.id,
            user_id=user.id,
            user_email=user.email,
            is_verified=user.is_verified,
            ip_address=ip,
            char_limit=settings.free_api_char_limit,  # 1000 char for API
            req_per_day=settings.free_api_req_per_day,
            req_per_min=settings.free_api_req_per_min,
            is_web_ui=False,
        )

    # ── 2. Authorization: Bearer <jwt> (Web UI) ────────────────
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = await decode_token(token, "access", db)
        except AuthenticationError:
            raise

        user = await db.get(User, user_id)

        if not user or not user.is_active:
            raise ForbiddenError("Account disabled or banned")

        # Load user's active API key
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.user_id == user_id,
                ApiKey.is_active == True
            )
        )
        key = result.scalar_one_or_none()

        logger.debug(f"AUTH_JWT user_id={user_id} verified={user.is_verified} ip={ip}")
        return RequestContext(
            tier="registered",
            api_key=key.key if key else None,
            api_key_id=key.id if key else None,
            user_id=user_id,
            user_email=user.email,
            is_verified=user.is_verified,
            ip_address=ip,
            char_limit=settings.free_webui_char_limit,  # 2000 char for Web UI
            req_per_day=settings.free_webui_req_per_day,
            req_per_min=settings.free_webui_req_per_min,
            is_web_ui=is_own_origin(request),
        )

    # ── 3. Anonymous — own origin (Web UI) ─────────────────────
    if is_own_origin(request):
        logger.debug(f"AUTH_ANONYMOUS ip={ip}")
        return RequestContext(
            tier="anonymous",
            api_key=None,
            api_key_id=None,
            user_id=None,
            user_email=None,
            is_verified=False,
            ip_address=ip,
            char_limit=settings.anon_char_limit,  # 500 char
            req_per_day=settings.anon_req_per_day,
            req_per_min=settings.anon_req_per_min,
            is_web_ui=True,
        )

    # ── 4. External without auth → 403 ────────────────────────
    logger.debug(f"AUTH_EXTERNAL_BLOCK ip={ip}")
    raise ForbiddenError(
        f"API access requires registration. "
        f"Get your free API key at https://{settings.public_domain}"
    )
