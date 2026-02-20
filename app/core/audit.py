"""
eidosSpeech v2 — Audit Logging
Helper functions for logging security-critical events to database.
"""

import json
import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_audit_event(
    db: AsyncSession,
    action: str,
    ip_address: str,
    user_id: Optional[int] = None,
    resource: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
):
    """
    Log security-critical event to audit_logs table.
    
    Args:
        db: Database session
        action: Action type (e.g., 'password_reset', 'api_key_regen', 'admin_ban_user')
        ip_address: Client IP address
        user_id: User ID (if applicable)
        resource: Resource identifier (e.g., 'user:123', 'api_key:456')
        user_agent: User agent string
        details: Additional context as dict (will be JSON serialized)
    
    Examples:
        await log_audit_event(db, 'password_reset', '1.2.3.4', user_id=123)
        await log_audit_event(db, 'admin_ban_user', '1.2.3.4', resource='user:456', 
                             details={'reason': 'spam'})
    """
    from app.db.models import AuditLog
    
    try:
        details_json = json.dumps(details) if details else None
        
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,  # Truncate
            details=details_json[:1000] if details_json else None,  # Truncate
            timestamp=datetime.now(timezone.utc),
        )
        
        db.add(audit_entry)
        await db.flush()  # Don't commit - let caller handle transaction
        
        logger.info(
            f"AUDIT action={action} user_id={user_id} resource={resource} ip={ip_address}"
        )
    except Exception as e:
        logger.error(f"AUDIT_LOG_ERROR action={action} error={e}")
        # Don't raise - audit logging failure shouldn't break main flow


async def log_login_attempt(
    db: AsyncSession,
    email: str,
    ip_address: str,
    success: bool,
    user_agent: Optional[str] = None,
):
    """
    Log login attempt for brute-force detection.
    
    Args:
        db: Database session
        email: Email address attempted
        ip_address: Client IP
        success: Whether login succeeded
        user_agent: User agent string
    """
    from app.db.models import LoginAttempt
    
    try:
        attempt = LoginAttempt(
            email=email.lower(),
            ip_address=ip_address,
            success=success,
            user_agent=user_agent[:500] if user_agent else None,
            timestamp=datetime.now(timezone.utc),
        )
        
        db.add(attempt)
        await db.flush()
        
        if not success:
            logger.warning(f"LOGIN_FAIL email={email} ip={ip_address}")
    except Exception as e:
        logger.error(f"LOGIN_ATTEMPT_LOG_ERROR email={email} error={e}")


async def get_recent_failed_logins(
    db: AsyncSession,
    email: str,
    minutes: int = 15,
) -> int:
    """
    Count recent failed login attempts for an email.
    Used for brute-force detection.
    
    Args:
        db: Database session
        email: Email to check
        minutes: Time window in minutes
    
    Returns:
        Number of failed attempts in the time window
    """
    from app.db.models import LoginAttempt
    from sqlalchemy import select, func
    from datetime import timedelta
    
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        result = await db.execute(
            select(func.count(LoginAttempt.id))
            .where(
                LoginAttempt.email == email.lower(),
                LoginAttempt.success == False,
                LoginAttempt.timestamp >= cutoff,
            )
        )
        
        count = result.scalar() or 0
        return count
    except Exception as e:
        logger.error(f"FAILED_LOGIN_COUNT_ERROR email={email} error={e}")
        return 0  # Fail open - don't block on error
