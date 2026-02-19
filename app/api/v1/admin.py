"""
eidosSpeech v2 — Admin API
7 admin endpoints protected by X-Admin-Key header.
Admin dashboard: stats, users, usage, ban, blacklist.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_

from app.config import settings
from app.core.exceptions import ForbiddenError
from app.core.cache import get_cache
from app.db.database import get_db
from app.db.models import User, ApiKey, DailyUsage, TokenRevocation, Blacklist
from app.models.schemas import AdminBlacklistRequest, MessageResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_admin_key(request: Request):
    """Dependency — validates X-Admin-Key header"""
    key = request.headers.get("x-admin-key", "")
    if not key or key != settings.admin_key:
        logger.warning(f"ADMIN_AUTH_FAIL ip={request.client.host if request.client else 'unknown'}")
        raise ForbiddenError("Invalid or missing admin key")
    return key


# ── GET /admin/stats ───────────────────────────────────────────────────────────
@router.get("/stats", dependencies=[Depends(verify_admin_key)])
async def admin_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate system stats"""
    today = date.today()
    yesterday = today - timedelta(days=1)

    total_users = (await db.execute(func.count(User.id))).scalar() or 0
    verified_users = (await db.execute(
        select(func.count(User.id)).where(User.is_verified == True)
    )).scalar() or 0
    active_keys = (await db.execute(
        select(func.count(ApiKey.id)).where(ApiKey.is_active == True)
    )).scalar() or 0

    requests_today = (await db.execute(
        select(func.sum(DailyUsage.request_count)).where(DailyUsage.date == today)
    )).scalar() or 0

    requests_yesterday = (await db.execute(
        select(func.sum(DailyUsage.request_count)).where(DailyUsage.date == yesterday)
    )).scalar() or 0

    cache = get_cache()

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "active_api_keys": active_keys,
        "requests_today": requests_today,
        "requests_yesterday": requests_yesterday,
        "cache": cache.stats(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── GET /admin/users ───────────────────────────────────────────────────────────
@router.get("/users", dependencies=[Depends(verify_admin_key)])
async def admin_users(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
):
    """Paginated user list with search and sort"""
    today = date.today()
    offset = (page - 1) * per_page

    query = select(User)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(User, sort, User.created_at)
    if order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)

    query = query.offset(offset).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()

    user_list = []
    for u in users:
        # Get active API key
        key_result = await db.execute(
            select(ApiKey).where(ApiKey.user_id == u.id, ApiKey.is_active == True)
        )
        key = key_result.scalar_one_or_none()

        # Today's usage
        usage_today = 0
        if key:
            usage_result = await db.execute(
                select(func.sum(DailyUsage.request_count)).where(
                    DailyUsage.api_key_id == key.id,
                    DailyUsage.date == today,
                )
            )
            usage_today = usage_result.scalar() or 0

        user_list.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_verified": u.is_verified,
            "is_active": u.is_active,
            "api_key": key.key[:12] + "..." if key else None,
            "usage_today": usage_today,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "users": user_list,
    }


# ── GET /admin/usage ───────────────────────────────────────────────────────────
@router.get("/usage", dependencies=[Depends(verify_admin_key)])
async def admin_usage(
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=90),
):
    """Daily usage aggregates for last N days"""
    cutoff = date.today() - timedelta(days=days)

    result = await db.execute(
        select(
            DailyUsage.date,
            func.sum(DailyUsage.request_count).label("requests"),
            func.sum(DailyUsage.chars_used).label("chars"),
            func.count(func.distinct(DailyUsage.ip_address)).label("unique_ips"),
        )
        .where(DailyUsage.date >= cutoff)
        .group_by(DailyUsage.date)
        .order_by(DailyUsage.date)
    )
    rows = result.all()

    return {
        "days": [
            {
                "date": str(r.date),
                "requests": r.requests or 0,
                "chars": r.chars or 0,
                "unique_ips": r.unique_ips or 0,
            }
            for r in rows
        ]
    }


# ── GET /admin/usage/voices ────────────────────────────────────────────────────
@router.get("/usage/voices", dependencies=[Depends(verify_admin_key)])
async def admin_voice_usage(
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
):
    """Popular voices over last N days"""
    cutoff = date.today() - timedelta(days=days)

    result = await db.execute(
        select(
            DailyUsage.voice,
            func.sum(DailyUsage.request_count).label("count"),
        )
        .where(DailyUsage.date >= cutoff, DailyUsage.voice != None)
        .group_by(DailyUsage.voice)
        .order_by(desc("count"))
        .limit(limit)
    )
    rows = result.all()

    return {
        "voices": [{"voice": r.voice, "count": r.count} for r in rows],
        "days": days,
    }


# ── POST /admin/keys/{key_id}/disable ─────────────────────────────────────────
@router.post("/keys/{key_id}/disable", dependencies=[Depends(verify_admin_key)])
async def admin_disable_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Disable an API key"""
    key = await db.get(ApiKey, key_id)
    if not key:
        raise ForbiddenError("API key not found")

    key.is_active = False
    await db.commit()

    logger.info(f"ADMIN_ACTION action=disable_key key_id={key_id}")
    return {"message": f"API key {key_id} disabled successfully"}


# ── POST /admin/users/{user_id}/ban ───────────────────────────────────────────
@router.post("/users/{user_id}/ban", dependencies=[Depends(verify_admin_key)])
async def admin_ban_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Ban a user: set is_active=False, disable their API key"""
    user = await db.get(User, user_id)
    if not user:
        raise ForbiddenError("User not found")

    user.is_active = False

    # Disable all API keys
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id)
    )
    for key in result.scalars().all():
        key.is_active = False

    await db.commit()

    logger.info(f"ADMIN_ACTION action=ban_user user_id={user_id} email={user.email}")
    return {"message": f"User {user.email} has been banned"}


# ── POST /admin/blacklist ──────────────────────────────────────────────────────
@router.post("/blacklist", dependencies=[Depends(verify_admin_key)])
async def admin_blacklist(
    body: AdminBlacklistRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add IP or email to permanent blacklist"""
    entry = Blacklist(
        type=body.type,
        value=body.value,
        reason=body.reason,
    )
    db.add(entry)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        return {"message": f"{body.type} '{body.value}' is already blacklisted"}

    logger.info(f"ADMIN_ACTION action=blacklist type={body.type} value={body.value}")
    return {"message": f"{body.type} '{body.value}' added to blacklist"}


# ── GET /admin/blacklist ───────────────────────────────────────────────────────
@router.get("/blacklist", dependencies=[Depends(verify_admin_key)])
async def get_blacklist(db: AsyncSession = Depends(get_db)):
    """List all blacklisted IPs and emails"""
    result = await db.execute(select(Blacklist).order_by(desc(Blacklist.created_at)))
    entries = result.scalars().all()
    return {
        "entries": [
            {
                "id": e.id,
                "type": e.type,
                "value": e.value,
                "reason": e.reason,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]
    }
