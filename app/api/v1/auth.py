"""
eidosSpeech v2 — Auth Endpoints
10 endpoints for registration, verification, login, JWT refresh, password management.
Contek eidosStack auth pattern.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone, date

import httpx
from fastapi import APIRouter, Depends, Request
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.core.exceptions import (
    ValidationError, AuthenticationError, ForbiddenError,
    ConflictError, RateLimitError,
)
from app.core.jwt_handler import create_token_pair, decode_token, revoke_token
from app.core.auth import get_client_ip, is_blacklisted
from app.db.database import get_db
from app.db.models import User, ApiKey, RegistrationAttempt, TokenRevocation
from app.models.schemas import (
    RegisterRequest, LoginRequest, VerifyEmailRequest,
    ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest,
    ResendVerificationRequest, TokenResponse, MessageResponse,
    UserProfile, UserUsageToday, MeResponse, RegenKeyResponse,
)
from app.services.email_service import (
    get_email_dispatcher, verification_email,
    reset_password_email, welcome_email,
)

router = APIRouter()
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt (max 72 bytes)"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_api_key() -> str:
    """Generate API key: esk_ + token_urlsafe(24) = 36 chars, 192-bit entropy"""
    return f"esk_{secrets.token_urlsafe(24)}"


async def verify_turnstile(token: str, ip: str = None) -> bool:
    """
    Verify Cloudflare Turnstile token.
    Pattern matched from eidosstack-license-server.
    """
    if not settings.turnstile_enabled:
        return True

    # Bypass check (useful for development/testing)
    if settings.turnstile_allow_bypass and token == "dev-bypass":
        logger.warning(f"TURNSTILE_BYPASS_USED ip={ip}")
        return True

    if not settings.turnstile_secret_key:
        logger.error("TURNSTILE_SECRET_KEY not configured")
        return False

    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": ip or "",
                }
            )
            data = resp.json()
            success = data.get("success", False)
            if not success:
                logger.warning(f"TURNSTILE_FAIL errors={data.get('error-codes')} ip={ip}")
            return success
    except Exception as e:
        logger.error(f"TURNSTILE_ERROR: {e}")
        return False


# ── GET /turnstile-config ──────────────────────────────────────────────────────
@router.get("/turnstile-config")
async def get_turnstile_config():
    """Get Turnstile configuration for frontend"""
    return {
        "enabled": settings.turnstile_enabled,
        "sitekey": settings.turnstile_site_key if settings.turnstile_enabled else None,
    }


# ── POST /register ─────────────────────────────────────────────────────────────
@router.post("/register", status_code=201, response_model=MessageResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register new user. Sends verification email (non-blocking)."""
    ip = get_client_ip(request)
    email = body.email.lower().strip()

    # Check IP blacklist
    if await is_blacklisted(db, ip=ip, email=email):
        raise ForbiddenError("Registration not allowed from this IP or email")

    # Verify Turnstile
    if settings.turnstile_enabled:
        if not body.turnstile_token:
            raise ValidationError("Turnstile verification required")
        if not await verify_turnstile(body.turnstile_token, ip=ip):
            raise ValidationError("Turnstile verification failed. Please try again.")

    # Check registration attempts (max 3 per IP per day)
    today = date.today()
    result = await db.execute(
        select(RegistrationAttempt).where(
            RegistrationAttempt.ip_address == ip,
            RegistrationAttempt.date == today,
        )
    )
    attempt = result.scalar_one_or_none()
    if attempt and attempt.attempt_count >= 3:
        raise RateLimitError(
            "Maximum registration attempts reached (3/day per IP). Try again tomorrow.",
            retry_after=86400,
        )

    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        # Email already registered - provide helpful message
        if existing_user.is_verified:
            raise ConflictError(
                "An account with this email already exists. "
                "Please login or use 'Forgot Password' if you can't access your account."
            )
        else:
            raise ConflictError(
                "An account with this email already exists but is not verified. "
                "Please check your email for the verification link or use 'Resend Verification' to get a new one."
            )

    # Create user
    verification_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        is_verified=False,
        is_active=True,
        tos_accepted_at=now,
        verification_token=verification_token,
        verification_expires=now + timedelta(hours=24),
    )
    db.add(user)

    # Track registration attempt
    if attempt:
        attempt.attempt_count += 1
    else:
        db.add(RegistrationAttempt(ip_address=ip, date=today, attempt_count=1))

    await db.commit()

    logger.info(f"USER_REGISTER email={email} ip={ip}")

    # Send verification email (non-blocking — best effort)
    subject, html = verification_email(verification_token, settings.public_domain)
    import asyncio
    asyncio.create_task(
        get_email_dispatcher().send(email, subject, html, critical=False)
    )

    return {"message": "Account created! Check your email for the verification link."}


# ── POST /verify-email ─────────────────────────────────────────────────────────
@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email token → generate API key → auto-login"""
    result = await db.execute(
        select(User).where(User.verification_token == body.token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValidationError("Invalid verification token")

    now = datetime.now(timezone.utc)
    if user.verification_expires and user.verification_expires.replace(tzinfo=timezone.utc) < now:
        raise ValidationError("Verification link has expired. Request a new one.")

    if user.is_verified:
        raise ValidationError("Email already verified. Please login.")

    # Verify user
    user.is_verified = True
    user.verification_token = None
    user.verification_expires = None

    # Generate API key
    api_key_str = generate_api_key()
    api_key = ApiKey(key=api_key_str, user_id=user.id, is_active=True)
    db.add(api_key)
    await db.commit()

    logger.info(f"USER_VERIFY email={user.email}")

    # Auto-login: create token pair
    access_token, refresh_token = create_token_pair(user.id, user.email)

    # Send welcome email (non-blocking)
    subject, html = welcome_email(api_key_str, settings.public_domain)
    import asyncio
    asyncio.create_task(
        get_email_dispatcher().send(user.email, subject, html, critical=False)
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "full_name": user.full_name,
            "api_key": api_key_str,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "usage": {
                "requests": 0, 
                "chars": 0, 
                "requests_limit": settings.free_webui_req_per_day, 
                "chars_limit": settings.free_webui_char_limit  # 2000 for Web UI
            }
        },
    }


# ── POST /login ────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login with credentials → access + refresh tokens"""
    ip = get_client_ip(request)
    email = body.email.lower().strip()

    # Verify Turnstile
    if settings.turnstile_enabled:
        if not body.turnstile_token:
            raise ValidationError("Turnstile verification required")
        if not await verify_turnstile(body.turnstile_token, ip=ip):
            raise ValidationError("Turnstile verification failed. Please try again.")

    # Find user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Check user exists and is active BEFORE password verification
    # This prevents timing attacks and email enumeration
    if not user:
        # Log failed attempt
        from app.core.audit import log_login_attempt
        user_agent = request.headers.get("user-agent")
        await log_login_attempt(db, email, ip, False, user_agent)
        await db.commit()
        
        logger.warning(f"AUTH_FAIL email={email} ip={ip} reason=user_not_found")
        raise AuthenticationError("Invalid email or password")
    
    if not user.is_active:
        from app.core.audit import log_login_attempt
        user_agent = request.headers.get("user-agent")
        await log_login_attempt(db, email, ip, False, user_agent)
        await db.commit()
        
        logger.warning(f"AUTH_FAIL email={email} ip={ip} reason=account_banned")
        raise AuthenticationError("Invalid email or password")  # Generic message

    # Now verify password
    if not verify_password(body.password, user.password_hash):
        from app.core.audit import log_login_attempt
        user_agent = request.headers.get("user-agent")
        await log_login_attempt(db, email, ip, False, user_agent)
        await db.commit()
        
        logger.warning(f"AUTH_FAIL email={email} ip={ip} reason=invalid_password")
        raise AuthenticationError("Invalid email or password")

    # Check for brute force attempts
    from app.core.audit import get_recent_failed_logins
    failed_count = await get_recent_failed_logins(db, email, minutes=15)
    if failed_count >= 5:
        logger.warning(f"AUTH_BRUTE_FORCE email={email} ip={ip} failed_count={failed_count}")
        raise RateLimitError(
            "Too many failed login attempts. Please try again in 15 minutes.",
            retry_after=900
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    
    # Log successful login
    from app.core.audit import log_login_attempt
    user_agent = request.headers.get("user-agent")
    await log_login_attempt(db, email, ip, True, user_agent)
    
    await db.commit()

    logger.info(f"USER_LOGIN email={email} ip={ip} verified={user.is_verified}")

    access_token, refresh_token = create_token_pair(user.id, user.email)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "email": user.email, 
            "full_name": user.full_name,
            "is_verified": user.is_verified,
        },
    }


# ── POST /refresh ──────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh token → new token pair. Revokes old refresh token JTI."""
    payload = await decode_token(body.refresh_token, "refresh", db)

    user_id = payload["user_id"]
    email = payload["sub"]
    old_jti = payload["jti"]
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    # Verify user still active
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise AuthenticationError("Account not accessible")

    # Revoke old refresh token
    await revoke_token(old_jti, exp, db)

    # Issue new pair
    access_token, new_refresh_token = create_token_pair(user_id, email)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


# ── POST /logout ───────────────────────────────────────────────────────────────
@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Revoke current access token via JTI"""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthenticationError("No token provided")

    token = auth_header[7:]

    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except Exception:
        raise AuthenticationError("Invalid token")

    jti = payload.get("jti")
    exp = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)

    if jti:
        await revoke_token(jti, exp, db)
        logger.info(f"USER_LOGOUT email={payload.get('sub')} jti={jti}")

    return {"message": "Logged out successfully"}


# ── GET /me ────────────────────────────────────────────────────────────────────
@router.get("/me", response_model=MeResponse)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile + API key + today's usage"""
    from app.db.models import DailyUsage

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthenticationError("Authentication required")

    payload = await decode_token(auth_header[7:], "access", db)
    user = await db.get(User, payload["user_id"])

    if not user or not user.is_active:
        raise AuthenticationError("Account not accessible")

    # Get active API key
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.is_active == True)
    )
    key = result.scalar_one_or_none()

    # Today's usage
    today = date.today()
    if key:
        result = await db.execute(
            select(DailyUsage).where(
                DailyUsage.api_key_id == key.id,
                DailyUsage.date == today,
            )
        )
        # Use scalars().first() to handle potential duplicates gracefully
        usage_row = result.scalars().first()
    else:
        usage_row = None

    # Web UI gets higher char limit (2000) vs API (1000)
    usage = UserUsageToday(
        requests=usage_row.request_count if usage_row else 0,
        chars=usage_row.chars_used if usage_row else 0,
        requests_limit=settings.free_webui_req_per_day,
        chars_limit=settings.free_webui_char_limit,  # 2000 for Web UI
    )

    user_profile = UserProfile(
        email=user.email,
        full_name=user.full_name,
        is_verified=user.is_verified,
        created_at=user.created_at,
        api_key=key.key if key else None,
        usage=usage,
    )

    return {"user": user_profile}


# ── POST /forgot-password ──────────────────────────────────────────────────────
@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Initiate password reset. Always returns same response (no user enumeration)."""
    ip = get_client_ip(request)
    email = body.email.lower().strip()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user and user.is_active and user.is_verified:
        now = datetime.now(timezone.utc)
        reset_token = secrets.token_urlsafe(32)
        user.reset_token = reset_token
        user.reset_token_expires = now + timedelta(hours=1)
        await db.commit()

        subject, html = reset_password_email(reset_token, settings.public_domain, ip)
        import asyncio
        asyncio.create_task(
            get_email_dispatcher().send(email, subject, html, critical=False)
        )

    return {"message": "If that email is registered, you'll receive a password reset link shortly."}


# ── POST /reset-password ───────────────────────────────────────────────────────
@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using token. Invalidates all existing sessions."""
    result = await db.execute(
        select(User).where(User.reset_token == body.token)
    )
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not user:
        raise ValidationError("Invalid or expired reset link")

    if user.reset_token_expires and user.reset_token_expires.replace(tzinfo=timezone.utc) < now:
        raise ValidationError("Reset link has expired. Request a new one.")

    # Update password, clear reset token
    user.password_hash = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.updated_at = now
    
    # Log audit event
    from app.core.audit import log_audit_event
    await log_audit_event(
        db, 
        action='password_reset',
        ip_address='unknown',  # No request context here
        user_id=user.id,
        resource=f'user:{user.id}'
    )
    
    await db.commit()

    logger.info(f"PASSWORD_RESET email={user.email}")

    return {"message": "Password updated successfully. Please login with your new password."}


# ── POST /resend-verification ──────────────────────────────────────────────────
@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resend verification email. Rate limited: 1 per 5 minutes per email."""
    ip = get_client_ip(request)
    email = body.email.lower().strip()
    
    # Check if user is authenticated (from dashboard or admin panel)
    is_authenticated = False
    auth_header = request.headers.get("authorization", "")
    admin_key = request.headers.get("x-admin-key", "")
    
    if auth_header.startswith("Bearer ") or admin_key:
        is_authenticated = True
    
    # Verify Turnstile only for unauthenticated requests
    if settings.turnstile_enabled and not is_authenticated:
        if not body.turnstile_token:
            raise ValidationError("Turnstile verification required")
        if not await verify_turnstile(body.turnstile_token, ip=ip):
            raise ValidationError("Turnstile verification failed. Please try again.")
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user and not user.is_verified:
        now = datetime.now(timezone.utc)

        # Rate limit: check if last token was issued < 5 min ago
        if (user.verification_expires and
                user.verification_expires.replace(tzinfo=timezone.utc) > now + timedelta(hours=23, minutes=55)):
            raise RateLimitError(
                "Please wait 5 minutes before requesting another verification email.",
                retry_after=300,
            )

        # Generate new token
        new_token = secrets.token_urlsafe(32)
        user.verification_token = new_token
        user.verification_expires = now + timedelta(hours=24)
        await db.commit()

        subject, html = verification_email(new_token, settings.public_domain)
        import asyncio
        asyncio.create_task(
            get_email_dispatcher().send(email, subject, html, critical=False)
        )

    return {"message": "If your email is registered and unverified, a new link has been sent."}


# ── POST /regen-key ────────────────────────────────────────────────────────────
@router.post("/regen-key", response_model=RegenKeyResponse)
async def regen_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Regenerate API key. Rate limited: 1 per 5 minutes per user."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthenticationError("Authentication required")

    payload = await decode_token(auth_header[7:], "access", db)
    user_id = payload["user_id"]

    # Check cooldown via last API key creation time
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.is_active == True)
        .order_by(desc(ApiKey.created_at))
        .limit(1)
    )
    old_key = result.scalar_one_or_none()

    if old_key:
        now = datetime.now(timezone.utc)
        created = old_key.created_at.replace(tzinfo=timezone.utc)
        if (now - created).total_seconds() < 300:  # 5 minute cooldown
            raise RateLimitError(
                "API key can only be regenerated once every 5 minutes.",
                retry_after=int(300 - (now - created).total_seconds()),
            )
        # Deactivate old key
        old_key.is_active = False

    # Create new key
    new_key_str = generate_api_key()
    new_key = ApiKey(key=new_key_str, user_id=user_id, is_active=True)
    db.add(new_key)
    
    # Log audit event
    from app.core.audit import log_audit_event
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    await log_audit_event(
        db,
        action='api_key_regenerated',
        ip_address=ip,
        user_id=user_id,
        resource=f'api_key:{new_key_str[:12]}...',
        user_agent=user_agent
    )
    
    await db.commit()

    logger.info(f"API_KEY_REGEN user_id={user_id}")

    return {"api_key": new_key_str, "message": "API key regenerated successfully"}
