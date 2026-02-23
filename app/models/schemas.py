"""
eidosSpeech v2 — Pydantic Schemas
Request/response models for all API endpoints.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── TTS Schemas ───────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice: str = Field(default="id-ID-GadisNeural", description="Voice ID (e.g., id-ID-GadisNeural)")
    rate: str = Field(default="+0%", description="Speech rate e.g. +10%, -5%")
    pitch: str = Field(default="+0Hz", description="Pitch e.g. +5Hz, -10Hz")
    volume: str = Field(default="+0%", description="Volume e.g. +10%, -5%")
    style: Optional[str] = Field(
        default=None,
        description="Voice emotion/style (cheerful, sad, whispering, etc.) - only for supported voices"
    )
    style_degree: Optional[float] = Field(
        default=None,
        ge=0.01,
        le=2.0,
        description="Style intensity 0.01-2.0 (1.0 = normal, 2.0 = maximum)"
    )

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("text cannot be empty")
        return v


class TTSSubtitleRequest(TTSRequest):
    words_per_cue: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Words per subtitle cue line (1-50)"
    )


class ScriptRequest(BaseModel):
    script: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Multi-voice script in [Speaker] text format"
    )
    voice_map: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of speaker names to voice IDs"
    )
    pause_ms: int = Field(
        default=500,
        ge=0,
        le=3000,
        description="Pause duration between lines in milliseconds"
    )
    rate: str = Field(default="+0%", description="Speech rate for all voices")
    pitch: str = Field(default="+0Hz", description="Pitch for all voices")
    volume: str = Field(default="+0%", description="Volume for all voices")

    @field_validator("script")
    @classmethod
    def script_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("script cannot be empty")
        # Check max lines
        lines = [l for l in v.split('\n') if l.strip()]
        if len(lines) > 50:
            raise ValueError("script cannot exceed 50 lines")
        return v


class TTSResponse(BaseModel):
    """Used for tracking/logging (actual response is FileResponse)"""
    voice: str
    duration_ms: Optional[int] = None
    cached: bool = False
    cache_key: str = ""


# ── Auth Schemas ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="8-128 characters")
    full_name: Optional[str] = Field(None, max_length=255)
    tos_accepted: bool = Field(..., description="Must be true to register")
    turnstile_token: Optional[str] = None

    @field_validator("tos_accepted")
    @classmethod
    def must_accept_tos(cls, v):
        if not v:
            raise ValueError("You must accept the Terms of Service to register")
        return v
    
    @field_validator("full_name")
    @classmethod
    def sanitize_name(cls, v):
        if not v:
            return v
        # Remove HTML tags
        import re
        v = re.sub(r'<[^>]+>', '', v)
        # Remove excessive whitespace
        v = ' '.join(v.split())
        # Limit to alphanumeric + basic punctuation
        if not re.match(r'^[a-zA-Z0-9\s\.\-\']+$', v):
            raise ValueError("Name contains invalid characters. Only letters, numbers, spaces, dots, hyphens, and apostrophes allowed")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password cannot exceed 128 characters")
        
        # Check bcrypt byte limit (72 bytes)
        if len(v.encode('utf-8')) > 72:
            raise ValueError("Password is too long. Please use a shorter password (max 72 bytes)")
        
        # Check complexity requirements
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        
        if not has_upper:
            raise ValueError("Password must contain at least one uppercase letter")
        if not has_lower:
            raise ValueError("Password must contain at least one lowercase letter")
        if not has_digit:
            raise ValueError("Password must contain at least one number")
        
        # Check against common passwords
        common_passwords = [
            "password", "12345678", "qwerty", "abc123", "password123",
            "admin123", "letmein", "welcome", "monkey", "dragon"
        ]
        if v.lower() in common_passwords:
            raise ValueError("Password is too common. Please choose a stronger password")
        
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: Optional[str] = None  # Cloudflare Turnstile (if enabled)


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    turnstile_token: Optional[str] = None  # Cloudflare Turnstile (if enabled)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ── Auth Response Schemas ─────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


class UserUsageToday(BaseModel):
    requests: int
    chars: int
    requests_limit: int
    chars_limit: int


class UserProfile(BaseModel):
    email: str
    full_name: Optional[str]
    is_verified: bool
    created_at: datetime
    api_key: Optional[str] = None
    usage: Optional[UserUsageToday] = None


class RegenKeyResponse(BaseModel):
    api_key: str
    message: str = "API key regenerated successfully"


class MeResponse(BaseModel):
    user: UserProfile


# ── Voice Schemas ─────────────────────────────────────────────────────────────

class VoiceInfo(BaseModel):
    id: str
    name: str
    language: str
    language_code: str
    gender: str


class VoiceListResponse(BaseModel):
    voices: list[VoiceInfo]
    total: int


# ── Health Schemas ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    cache: dict
    uptime: float
    proxy: dict


# ── Admin Schemas ─────────────────────────────────────────────────────────────

class AdminStatsResponse(BaseModel):
    total_users: int
    verified_users: int
    active_api_keys: int
    requests_today: int
    requests_yesterday: int
    cache: dict


class AdminUserItem(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_verified: bool
    is_active: bool
    api_key: Optional[str]
    usage_today: int
    created_at: datetime


class AdminUsersResponse(BaseModel):
    total: int
    page: int
    per_page: int
    users: list[AdminUserItem]


class AdminUsageDay(BaseModel):
    date: str
    requests: int
    chars: int
    unique_ips: int


class AdminUsageResponse(BaseModel):
    days: list[AdminUsageDay]


class AdminVoiceUsage(BaseModel):
    voice: str
    count: int


class AdminBlacklistRequest(BaseModel):
    type: Literal["ip", "email"]
    value: str
    reason: Optional[str] = None


# ── Generic Response ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[dict] = None
