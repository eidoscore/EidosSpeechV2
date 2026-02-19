"""
eidosSpeech v2 — SQLAlchemy ORM Models
6 tables: users, api_keys, daily_usage, token_revocations, registration_attempts, blacklist
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    ForeignKey, func, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Registered users — email + password, email verification, account status"""
    __tablename__ = "users"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    email                = Column(String(255), unique=True, nullable=False, index=True)
    password_hash        = Column(String(255), nullable=False)               # bcrypt, salt 10
    full_name            = Column(String(255))
    is_verified          = Column(Boolean, default=False, nullable=False)
    is_active            = Column(Boolean, default=True, nullable=False)     # False = banned
    tos_accepted_at      = Column(DateTime, nullable=False)

    verification_token   = Column(String(64), unique=True)                   # secrets.token_urlsafe(32)
    verification_expires = Column(DateTime)                                  # created_at + 24h
    reset_token          = Column(String(64), unique=True)
    reset_token_expires  = Column(DateTime)                                  # created_at + 1h

    last_login_at        = Column(DateTime)
    created_at           = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_verification_token", "verification_token"),
        Index("idx_users_reset_token", "reset_token"),
    )


class ApiKey(Base):
    """API keys — format: esk_<token_urlsafe(24)>, 1 per user"""
    __tablename__ = "api_keys"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    key          = Column(String(64), unique=True, nullable=False, index=True)  # esk_xxx
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active    = Column(Boolean, default=True, nullable=False)
    created_at   = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
    )


class DailyUsage(Base):
    """Daily request/character tracking — per API key (registered) or IP (anonymous)"""
    __tablename__ = "daily_usage"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id    = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"))  # nullable (anonymous)
    ip_address    = Column(String(45))                                               # nullable (registered)
    date          = Column(Date, nullable=False)                                      # UTC date
    request_count = Column(Integer, default=0, nullable=False)
    chars_used    = Column(Integer, default=0, nullable=False)
    voice         = Column(String(100))                                               # track popular voices

    __table_args__ = (
        Index("idx_daily_usage_key_date", "api_key_id", "date"),
        Index("idx_daily_usage_ip_date", "ip_address", "date"),
    )


class TokenRevocation(Base):
    """Revoked JWT tokens — identified by JTI. Auto-cleaned after expiry."""
    __tablename__ = "token_revocations"

    jti        = Column(String(64), primary_key=True)   # JWT ID
    expires_at = Column(DateTime, nullable=False)        # auto-cleanup after this


class RegistrationAttempt(Base):
    """Track registration attempts per IP per day (max 3/IP/day)"""
    __tablename__ = "registration_attempts"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ip_address    = Column(String(45), nullable=False)
    date          = Column(Date, nullable=False)          # UTC date
    attempt_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("ip_address", "date", name="uq_reg_attempts_ip_date"),
    )


class Blacklist(Base):
    """Permanent blacklist for IPs and emails (admin action)"""
    __tablename__ = "blacklist"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    type       = Column(String(10), nullable=False)    # 'ip' or 'email'
    value      = Column(String(255), nullable=False)   # IP address or email
    reason     = Column(String(255))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_blacklist_type_value"),
    )
