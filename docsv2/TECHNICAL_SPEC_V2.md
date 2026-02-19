# eidosSpeech v2 — Technical Specification

> Companion doc untuk [MASTERPLAN_V2.md](./MASTERPLAN_V2.md)
> v1 architecture reference: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)

---

## System Architecture

```
                                    eidosSpeech v2
+------------------+       +---------------------------------------+       +------------------+
|                  |       |  FastAPI (uvicorn)                     |       |                  |
|  Web Browser     | <---> |                                       | <---> |  Microsoft Edge  |
|  (Landing/App/   |       |  +---------+  +----------+  +------+  |       |  TTS Service     |
|   Dashboard)     |       |  | API     |  | Auth     |  | Rate |  |       |  (WebSocket)     |
|                  |       |  | Layer   |  | Layer    |  | Limit|  |       +------------------+
+------------------+       |  +---------+  +----------+  +------+  |              |
                           |       |            |           |      |       +------------------+
+------------------+       |  +---------+  +----------+  +------+  |       |  Webshare Proxy  |
|                  |       |  | TTS     |  | Email    |  | Proxy|  | <---> |  (optional)      |
|  External API    | <---> |  | Engine  |  | Service  |  | Mgr  |  |       +------------------+
|  Consumers       |       |  +---------+  +----------+  +------+  |
|  (curl/SDK)      |       |       |                               |
|                  |       |  +---------+  +----------+            |
+------------------+       |  | Cache   |  | SQLite   |            |
                           |  | (file)  |  | (WAL)    |            |
                           |  +---------+  +----------+            |
                           +---------------------------------------+
                                      |            |
                               +-----------+ +-----------+
                               | /data/    | | /data/    |
                               | cache/    | | db/       |
                               +-----------+ +-----------+
```

---

## Project Structure (v2)

```
eidosSpeech/
├── app/
│   ├── __init__.py                  # Version "2.0.0"
│   ├── main.py                      # FastAPI app, lifespan, CORS, page routes, cleanup
│   ├── config.py                    # Pydantic Settings (20+ new settings, startup validation)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py          # Register auth + admin + TTS routers
│   │       ├── tts.py               # POST /api/v1/tts (with RequestContext + rate limiter)
│   │       ├── voices.py            # GET /api/v1/voices (public, unchanged)
│   │       ├── batch.py             # 410 Gone (batch = v1 only)
│   │       ├── health.py            # GET /api/v1/health (+ DB connectivity check)
│   │       ├── auth.py              # NEW: 10 auth endpoints
│   │       └── admin.py             # NEW: 7 admin endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py                  # REWRITE: resolve_request_context (was: API key check)
│   │   ├── cache.py                 # File-based cache (unchanged)
│   │   ├── exceptions.py            # Extended: RateLimitError, AuthError, ConflictError
│   │   ├── jwt_handler.py           # NEW: JWT create/decode, token types
│   │   └── rate_limiter.py          # NEW: Hybrid rate limiter (memory + SQLite)
│   │
│   ├── db/
│   │   ├── __init__.py              # NEW
│   │   ├── database.py              # NEW: SQLAlchemy async engine, session, WAL
│   │   ├── models.py                # NEW: ORM models (5 tables)
│   │   └── seed.py                  # NEW: DB init on startup
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tts_engine.py            # Modified: proxy parameter
│   │   ├── voice_service.py         # Unchanged
│   │   ├── batch_service.py         # Unchanged (batch.py returns 410)
│   │   ├── email_service.py         # NEW: Multi-provider (SMTP + Resend fallback)
│   │   └── proxy_manager.py         # NEW: Round-robin proxy
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py               # Extended: auth schemas, RequestContext
│   │
│   └── static/
│       ├── landing.html             # NEW: Landing page (dark theme)
│       ├── index.html               # REWRITE: TTS App (Tailwind dark, auth, ads)
│       ├── dashboard.html           # NEW: User dashboard
│       ├── admin.html               # NEW: Admin panel
│       ├── tos.html                 # NEW: Terms of Service
│       ├── verify-email.html        # NEW: Email verification
│       ├── reset-password.html      # NEW: Password reset
│       ├── api-docs.html            # NEW: Custom API docs
│       ├── css/
│       │   └── style.css            # Minimal custom (Tailwind handles most)
│       └── js/
│           ├── app.js               # Modified: auth integration, usage display
│           ├── api-client.js         # Modified: auth methods, auto-refresh on 401
│           ├── audio-player.js       # Unchanged
│           ├── auth.js               # NEW: Auth state manager (localStorage)
│           └── toast.js              # NEW: Toast notification system
│
├── data/                             # Docker volume mount
│   ├── cache/                        # TTS audio cache (from v1)
│   └── db/                           # NEW: SQLite database
│       └── eidosspeech.db
│
├── requirements.txt                  # Extended: 7 new deps
├── Dockerfile                        # Modified: /data/db directory
├── docker-compose.yml                # Unchanged
├── docker-compose.nginx.yml          # Modified: app_data volume
├── nginx.conf                        # Unchanged (Docker internal)
├── nginx-public.conf                 # NEW: Public domain config
├── .env.example                      # Rewritten: all new vars
└── .gitignore
```

### Layer Responsibilities

| Layer | Folder | Responsibility |
|-------|--------|---------------|
| **API** | `app/api/v1/` | Route handlers — auth, TTS, voices, admin, health |
| **Core** | `app/core/` | Cross-cutting — auth resolution, JWT, rate limiting, caching, exceptions |
| **DB** | `app/db/` | Database — SQLAlchemy models, engine, migrations |
| **Services** | `app/services/` | Business logic — TTS, email, proxy, voice listing |
| **Models** | `app/models/` | Pydantic schemas for request/response + ORM models in `db/` |
| **Static** | `app/static/` | Frontend — HTML pages, JS modules, CSS |

---

## Database Schema

### Engine: SQLite + SQLAlchemy async

- Driver: `aiosqlite`
- Connection: `sqlite+aiosqlite:///./data/eidosspeech.db`
- WAL mode enabled on startup (`PRAGMA journal_mode=WAL`)
- Single file, persistent via Docker volume

### Tables

```sql
-- ============================================================
-- users
-- ============================================================
CREATE TABLE users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    email                 VARCHAR(255) UNIQUE NOT NULL,
    password_hash         VARCHAR(255) NOT NULL,          -- bcrypt, salt 10
    full_name             VARCHAR(255),
    is_verified           BOOLEAN DEFAULT FALSE,
    is_active             BOOLEAN DEFAULT TRUE,           -- false = banned
    tos_accepted_at       DATETIME NOT NULL,
    verification_token    VARCHAR(64) UNIQUE,             -- secrets.token_urlsafe(32)
    verification_expires  DATETIME,                       -- created_at + 24h
    reset_token           VARCHAR(64) UNIQUE,
    reset_token_expires   DATETIME,                       -- created_at + 1h
    last_login_at         DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_verification_token ON users(verification_token);
CREATE INDEX idx_users_reset_token ON users(reset_token);

-- ============================================================
-- api_keys
-- ============================================================
CREATE TABLE api_keys (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    key           VARCHAR(64) UNIQUE NOT NULL,           -- format: esk_<token_urlsafe(24)>
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at  DATETIME
);

CREATE INDEX idx_api_keys_key ON api_keys(key);          -- fast lookup
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);

-- ============================================================
-- daily_usage
-- ============================================================
CREATE TABLE daily_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id    INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,  -- nullable (anonymous)
    ip_address    VARCHAR(45),                           -- nullable (registered may not track IP)
    date          DATE NOT NULL,                         -- UTC date, new row per day
    request_count INTEGER DEFAULT 0,
    chars_used    INTEGER DEFAULT 0
);

CREATE INDEX idx_daily_usage_key_date ON daily_usage(api_key_id, date);
CREATE INDEX idx_daily_usage_ip_date ON daily_usage(ip_address, date);

-- ============================================================
-- token_revocations
-- ============================================================
CREATE TABLE token_revocations (
    jti           VARCHAR(64) PRIMARY KEY,               -- JWT ID from token
    expires_at    DATETIME NOT NULL                      -- auto-cleanup after expiry
);

-- ============================================================
-- registration_attempts
-- ============================================================
CREATE TABLE registration_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address    VARCHAR(45) NOT NULL,
    date          DATE NOT NULL,                         -- UTC date
    attempt_count INTEGER DEFAULT 0
);

CREATE UNIQUE INDEX idx_reg_attempts_ip_date ON registration_attempts(ip_address, date);

-- ============================================================
-- blacklist
-- ============================================================
CREATE TABLE blacklist (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          VARCHAR(10) NOT NULL,                  -- 'ip' or 'email'
    value         VARCHAR(255) NOT NULL,                 -- IP address or email
    reason        VARCHAR(255),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_blacklist_type_value ON blacklist(type, value);
```

### ORM Models

```python
# app/db/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    tos_accepted_at = Column(DateTime, nullable=False)
    verification_token = Column(String(64), unique=True)
    verification_expires = Column(DateTime)
    reset_token = Column(String(64), unique=True)
    reset_token_expires = Column(DateTime)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_used_at = Column(DateTime)

    user = relationship("User", back_populates="api_keys")

class DailyUsage(Base):
    __tablename__ = "daily_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"))
    ip_address = Column(String(45))
    date = Column(Date, nullable=False)
    request_count = Column(Integer, default=0)
    chars_used = Column(Integer, default=0)

class TokenRevocation(Base):
    __tablename__ = "token_revocations"
    jti = Column(String(64), primary_key=True)
    expires_at = Column(DateTime, nullable=False)

class RegistrationAttempt(Base):
    __tablename__ = "registration_attempts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False)
    date = Column(Date, nullable=False)
    attempt_count = Column(Integer, default=0)

class Blacklist(Base):
    __tablename__ = "blacklist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(10), nullable=False)       # 'ip' or 'email'
    value = Column(String(255), nullable=False)
    reason = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
```

---

## Authentication System

### JWT Token Structure

```python
# Access Token (15 min)
{
    "sub": "user@example.com",
    "user_id": 42,
    "type": "access",
    "jti": "unique-token-id",
    "iat": 1705000000,
    "exp": 1705000900     # +15 min
}

# Refresh Token (7 days)
{
    "sub": "user@example.com",
    "user_id": 42,
    "type": "refresh",
    "jti": "unique-token-id",
    "iat": 1705000000,
    "exp": 1705604800     # +7 days
}

# Verification Token — NOT JWT, uses secrets.token_urlsafe(32) stored in DB
# Reset Token — NOT JWT, uses secrets.token_urlsafe(32) stored in DB
```

### Auth Endpoints — Request/Response Specs

```
POST /api/v1/auth/register
  Request:  { email, password, full_name?, tos_accepted: true }
  Validate: email format, password 8-128 char, tos_accepted=true, not blacklisted
  Check:    registration_attempts < 3/IP/day, email not exists
  Action:   create user, send verification email (non-blocking)
  Response: 201 { message: "Check your email for verification link" }

POST /api/v1/auth/verify-email
  Request:  { token }
  Validate: token exists, not expired (24h)
  Action:   set is_verified=true, generate API key (esk_<random>), clear token
  Response: 200 { message, api_key: "esk_xxx", access_token, refresh_token }

POST /api/v1/auth/login
  Request:  { email, password, turnstile_token? }
  Validate: credentials, Turnstile (if enabled), user is_active, is_verified
  Action:   create access+refresh tokens, update last_login_at
  Response: 200 { access_token, refresh_token, user: { email, full_name } }

POST /api/v1/auth/refresh
  Request:  { refresh_token }
  Validate: token valid, type=refresh, not revoked (JTI check)
  Action:   revoke old JTI, create new token pair
  Response: 200 { access_token, refresh_token }

POST /api/v1/auth/logout
  Request:  Authorization: Bearer <access_token>
  Action:   revoke token JTI
  Response: 200 { message: "Logged out" }

GET /api/v1/auth/me
  Request:  Authorization: Bearer <access_token>
  Response: 200 { user: { email, full_name, is_verified, created_at },
                   api_key: "esk_xxx", usage: { today: { requests, chars }, limits } }

POST /api/v1/auth/forgot-password
  Request:  { email }
  Action:   generate reset token (1h expiry), send email (critical=true)
  Response: 200 { message: "If email exists, reset link sent" }  ← always same response

POST /api/v1/auth/reset-password
  Request:  { token, new_password }
  Validate: token exists, not expired (1h), password 8-128 char
  Action:   update password, clear token, revoke ALL user's JTIs
  Response: 200 { message: "Password updated. Please login again." }

POST /api/v1/auth/resend-verification
  Request:  { email }
  Rate:     1 per 5 min per email
  Action:   generate new token (24h), send email
  Response: 200 { message: "Verification email sent" }

POST /api/v1/auth/regen-key
  Request:  Authorization: Bearer <access_token>
  Rate:     1 per 5 min per user
  Action:   deactivate old key, create new key
  Response: 200 { api_key: "esk_new_xxx" }
```

### Request Context Resolution

```python
# app/core/auth.py

@dataclass
class RequestContext:
    tier: Literal["anonymous", "registered"]
    api_key: str | None
    api_key_id: int | None
    user_id: int | None
    ip_address: str
    char_limit: int
    req_per_day: int
    req_per_min: int
    is_web_ui: bool

async def resolve_request_context(request: Request, db: AsyncSession) -> RequestContext:
    """
    Resolution order:
    1. X-API-Key header → DB lookup → "registered"
    2. Authorization: Bearer <jwt> → decode → load user's API key → "registered"
    3. No credentials + Origin = own domain → "anonymous" (Web UI)
    4. No credentials + external Origin → 403 Forbidden
    """
    ip = get_client_ip(request)

    # Check blacklist first
    if await is_blacklisted(db, ip=ip):
        raise ForbiddenError("Access denied")

    # 1. API Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        key = await db.execute(select(ApiKey).where(ApiKey.key == api_key_header, ApiKey.is_active == True))
        key = key.scalar_one_or_none()
        if not key:
            raise ForbiddenError("Invalid API key")
        user = await db.get(User, key.user_id)
        if not user or not user.is_active:
            raise ForbiddenError("Account disabled")
        return RequestContext(
            tier="registered", api_key=key.key, api_key_id=key.id,
            user_id=user.id, ip_address=ip,
            char_limit=settings.free_char_limit, req_per_day=settings.free_req_per_day,
            req_per_min=settings.free_req_per_min, is_web_ui=False
        )

    # 2. Bearer JWT
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_jwt(token, expected_type="access")
        # ... load user + API key from DB ...
        return RequestContext(tier="registered", ..., is_web_ui=is_own_origin(request))

    # 3. Anonymous (Web UI only)
    if is_own_origin(request):
        return RequestContext(
            tier="anonymous", api_key=None, api_key_id=None,
            user_id=None, ip_address=ip,
            char_limit=settings.anon_char_limit, req_per_day=settings.anon_req_per_day,
            req_per_min=settings.anon_req_per_min, is_web_ui=True
        )

    # 4. External without auth
    raise ForbiddenError("Register for API access at https://eidosspeech.xyz")
```

### Origin Check

```python
def is_own_origin(request: Request) -> bool:
    """Check if request comes from our own domain (Web UI)"""
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    allowed = [
        f"https://{settings.public_domain}",
        f"http://{settings.public_domain}",
        "http://localhost:8000",     # dev
        "http://localhost:3000",     # dev
    ]
    return any(origin.startswith(a) or referer.startswith(a) for a in allowed)
```

---

## Rate Limiting System

### Architecture

```
Request → resolve_request_context → identity
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  RateLimiter     │
                              │                  │
                              │  ┌─────────────┐ │
                              │  │ Per-minute   │ │  ← in-memory (deque of timestamps)
                              │  │ sliding      │ │
                              │  │ window       │ │
                              │  └─────────────┘ │
                              │  ┌─────────────┐ │
                              │  │ Per-day      │ │  ← SQLite daily_usage table
                              │  │ counter      │ │
                              │  └─────────────┘ │
                              │  ┌─────────────┐ │
                              │  │ Concurrent   │ │  ← asyncio.Semaphore(1) per identity
                              │  │ limiter      │ │
                              │  └─────────────┘ │
                              └─────────────────┘
```

### Implementation

```python
# app/core/rate_limiter.py

class RateLimiter:
    def __init__(self):
        # Per-minute: in-memory sliding window
        self._minute_windows: dict[str, deque] = {}    # identity → deque of timestamps

        # Concurrent: per-identity semaphore
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_identity(self, ctx: RequestContext) -> str:
        """IP for anonymous, API key ID for registered"""
        if ctx.tier == "anonymous":
            return f"ip:{ctx.ip_address}"
        return f"key:{ctx.api_key_id}"

    async def check_and_consume(self, ctx: RequestContext, db: AsyncSession, text_len: int):
        """
        Check all limits. Raises RateLimitError if any exceeded.
        On success, increments counters.
        """
        identity = self._get_identity(ctx)

        # 1. Check character limit
        if text_len > ctx.char_limit:
            raise RateLimitError(f"Text too long. Max {ctx.char_limit} chars for {ctx.tier} tier.")

        # 2. Check per-minute (in-memory)
        now = time.time()
        window = self._minute_windows.setdefault(identity, deque())
        # Remove entries older than 60 seconds
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= ctx.req_per_min:
            raise RateLimitError("Per-minute limit exceeded", retry_after=60)

        # 3. Check per-day (SQLite)
        today = date.today()  # UTC
        usage = await get_or_create_daily_usage(db, ctx, today)
        if usage.request_count >= ctx.req_per_day:
            raise RateLimitError("Daily limit exceeded", retry_after=seconds_until_midnight_utc())

        # 4. Acquire concurrent semaphore (non-blocking)
        sem = self._semaphores.setdefault(identity, asyncio.Semaphore(1))
        if sem.locked():
            raise RateLimitError("Concurrent request limit. Wait for current request to finish.")

        # All checks passed — consume
        window.append(now)
        usage.request_count += 1
        usage.chars_used += text_len
        await db.commit()

    def get_headers(self, ctx: RequestContext, usage: DailyUsage) -> dict:
        """Generate X-RateLimit-* response headers"""
        return {
            "X-RateLimit-Tier": ctx.tier,
            "X-RateLimit-Limit-Day": str(ctx.req_per_day),
            "X-RateLimit-Remaining-Day": str(max(0, ctx.req_per_day - usage.request_count)),
            "X-RateLimit-Limit-Min": str(ctx.req_per_min),
            "X-RateLimit-Char-Limit": str(ctx.char_limit),
        }
```

---

## Email Service

### Multi-Provider Fallback (contek eidosStack)

```python
# app/services/email_service.py

class EmailProvider(ABC):
    name: str
    @abstractmethod
    async def send(self, to: str, subject: str, html: str) -> None: ...

class SmtpProvider(EmailProvider):
    """Generic SMTP via aiosmtplib — works with Brevo, Mailtrap, any SMTP"""
    def __init__(self, host, port, username, password, from_addr, name="SMTP"):
        self.name = name
        # ... store config ...

    async def send(self, to, subject, html):
        message = MIMEMultipart("alternative")
        message["From"] = self.from_addr
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(html, "html"))

        await aiosmtplib.send(message, hostname=self.host, port=self.port,
                              username=self.username, password=self.password,
                              use_tls=self.port == 465, start_tls=self.port == 587)

class ResendProvider(EmailProvider):
    """Resend REST API via httpx"""
    name = "Resend"
    def __init__(self, api_key, from_addr):
        self.api_key = api_key
        self.from_addr = from_addr

    async def send(self, to, subject, html):
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"from": self.from_addr, "to": [to], "subject": subject, "html": html})
            response.raise_for_status()

class EmailDispatcher:
    def __init__(self, settings):
        self.providers: list[EmailProvider] = []
        # Build provider chain from config
        if settings.smtp_host:
            self.providers.append(SmtpProvider(settings.smtp_host, ...))
        if settings.smtp_fallback_host:
            self.providers.append(SmtpProvider(settings.smtp_fallback_host, ..., name="SMTP-Fallback"))
        if settings.resend_api_key:
            self.providers.append(ResendProvider(settings.resend_api_key, settings.smtp_from))

    async def send(self, to: str, subject: str, html: str, critical: bool = False) -> bool:
        for provider in self.providers:
            try:
                await provider.send(to, subject, html)
                logger.info(f"EMAIL_SENT provider={provider.name} to={to}")
                return True
            except Exception as e:
                logger.warning(f"EMAIL_FAIL provider={provider.name} to={to} error={e}")
                continue

        logger.error(f"ALL_EMAIL_PROVIDERS_FAILED to={to}")
        if critical:
            raise EmailDeliveryError("All email providers failed")
        return False  # non-blocking
```

### Email Templates

Inline HTML strings — branded, dark theme, consistent:

```python
def verification_email(token: str, domain: str) -> tuple[str, str]:
    subject = "Verify your eidosSpeech account"
    html = f"""
    <div style="background:#0a0a0a; color:#f5f5f5; font-family:Inter,sans-serif; padding:40px; max-width:600px; margin:0 auto;">
        <h1 style="color:#10B981;">eidosSpeech</h1>
        <p>Click below to verify your email address:</p>
        <a href="https://{domain}/verify-email?token={token}"
           style="display:inline-block; background:#10B981; color:#fff; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:600;">
            Verify Email
        </a>
        <p style="color:#666; font-size:14px; margin-top:24px;">
            This link expires in 24 hours. If you didn't create an account, ignore this email.
        </p>
    </div>
    """
    return subject, html

def reset_password_email(token: str, domain: str, ip: str) -> tuple[str, str]:
    subject = "Reset your eidosSpeech password"
    html = f"""
    <div style="...same brand styling...">
        <h1 style="color:#10B981;">eidosSpeech</h1>
        <p>Click below to reset your password:</p>
        <a href="https://{domain}/reset-password?token={token}" style="...brand button...">
            Reset Password
        </a>
        <p style="color:#666; font-size:14px;">This link expires in 1 hour.</p>
        <p style="color:#666; font-size:12px;">Requested from IP: {ip}</p>
    </div>
    """
    return subject, html

def welcome_email(api_key: str, domain: str) -> tuple[str, str]:
    subject = "Welcome to eidosSpeech!"
    html = f"""
    <div style="...same brand styling...">
        <h1 style="color:#10B981;">Welcome to eidosSpeech!</h1>
        <p>Your API key:</p>
        <code style="background:#1e1e1e; padding:8px 16px; border-radius:4px; font-size:16px;">{api_key}</code>
        <p>Quick start:</p>
        <pre style="background:#1e1e1e; padding:16px; border-radius:8px; overflow-x:auto;">
curl -X POST https://{domain}/api/v1/tts \\
  -H "X-API-Key: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"text":"Hello world","voice":"id-ID-GadisNeural"}}'
        </pre>
        <a href="https://{domain}/dashboard" style="...brand button...">Go to Dashboard</a>
    </div>
    """
    return subject, html
```

---

## Proxy Manager

```python
# app/services/proxy_manager.py

class ProxyManager:
    MAX_FAILURES = 3

    def __init__(self, proxy_list: list[str]):
        self._proxies = proxy_list
        self._cycle = itertools.cycle(proxy_list) if proxy_list else None
        self._failures: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def get_next(self) -> str | None:
        """Return next healthy proxy URL, or None for direct connection"""
        if not self._proxies:
            return None

        async with self._lock:
            tried = 0
            while tried < len(self._proxies):
                proxy = next(self._cycle)
                if self._failures[proxy] < self.MAX_FAILURES:
                    return proxy
                tried += 1

            # All proxies failed — fallback to direct
            logger.warning("ALL_PROXIES_FAILED falling_back_to_direct")
            return None

    async def mark_success(self, proxy: str):
        self._failures[proxy] = 0

    async def mark_failure(self, proxy: str):
        self._failures[proxy] += 1
        if self._failures[proxy] >= self.MAX_FAILURES:
            logger.warning(f"PROXY_DISABLED proxy={proxy} failures={self._failures[proxy]}")

    def reset_all(self):
        """Called by periodic cleanup"""
        self._failures.clear()
```

Usage in TTS engine:

```python
# app/services/tts_engine.py
async def synthesize(self, text, voice, rate, pitch, volume) -> bytes:
    proxy_url = await self.proxy_manager.get_next()
    try:
        # edge-tts with proxy
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume,
                                            proxy=proxy_url)
        data = await communicate.save_to_buffer()
        if proxy_url:
            await self.proxy_manager.mark_success(proxy_url)
        return data
    except Exception as e:
        if proxy_url:
            await self.proxy_manager.mark_failure(proxy_url)
        raise
```

---

## TTS Endpoint (Modified)

```python
# app/api/v1/tts.py

@router.post("/tts")
async def generate_tts(
    request: TTSRequest,
    ctx: RequestContext = Depends(resolve_request_context),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    # 1. Rate limit check (char limit, per-min, per-day, concurrent)
    usage = await rate_limiter.check_and_consume(ctx, db, len(request.text))

    # 2. Cache check
    cache_key = compute_cache_key(request)
    cached = cache.get(cache_key)
    if cached:
        headers = rate_limiter.get_headers(ctx, usage)
        headers["X-Cache-Hit"] = "true"
        headers["X-Cache-Key"] = cache_key
        return FileResponse(cached, media_type="audio/mpeg", headers=headers)

    # 3. Acquire concurrent semaphore
    async with rate_limiter.acquire_concurrent(ctx):
        # 4. Generate via TTS engine (with proxy)
        audio_bytes = await tts_engine.synthesize(
            request.text, request.voice, request.rate, request.pitch, request.volume
        )

        # 5. Save to cache
        path = cache.put(cache_key, audio_bytes)

        # 6. Update API key last_used_at
        if ctx.api_key_id:
            await update_last_used(db, ctx.api_key_id)

        # 7. Return with rate limit headers
        headers = rate_limiter.get_headers(ctx, usage)
        headers["X-Cache-Hit"] = "false"
        headers["X-Cache-Key"] = cache_key
        return FileResponse(path, media_type="audio/mpeg", headers=headers)
```

---

## Admin API

### Authentication

```python
async def verify_admin_key(request: Request):
    key = request.headers.get("X-Admin-Key")
    if not key or key != settings.admin_key:
        raise ForbiddenError("Invalid admin key")
```

### Endpoints

```python
# app/api/v1/admin.py

@router.get("/stats")
# → { total_users, verified_users, active_api_keys, requests_today,
#     requests_yesterday, cache_stats: { files, size_mb, hit_rate } }

@router.get("/users")
# → { total, page, per_page, users: [{ id, email, full_name, is_verified,
#     is_active, api_key, usage_today, created_at }] }
# Query: ?page=1&per_page=20&search=email&sort=created_at&order=desc

@router.get("/usage")
# → { days: [{ date, requests, chars, unique_users }] }
# Query: ?days=30

@router.get("/usage/voices")
# → { voices: [{ voice, language, count }] }
# Query: ?days=7&limit=20

@router.post("/keys/{key_id}/disable")
# → disable API key, revoke all user's JTIs

@router.post("/users/{user_id}/ban")
# → set is_active=false, disable API key, revoke all JTIs

@router.post("/blacklist")
# Request: { type: "ip"|"email", value, reason? }
# → add to blacklist table
```

---

## Periodic Cleanup Tasks

```python
# app/main.py lifespan

async def periodic_cleanup():
    """Run every 1 hour"""
    while True:
        await asyncio.sleep(3600)
        async with get_db_session() as db:
            now = datetime.utcnow()

            # 1. Clean expired token revocations
            await db.execute(
                delete(TokenRevocation).where(TokenRevocation.expires_at < now)
            )

            # 2. Clean old registration attempts (> 7 days)
            cutoff = (now - timedelta(days=7)).date()
            await db.execute(
                delete(RegistrationAttempt).where(RegistrationAttempt.date < cutoff)
            )

            # 3. Delete unverified users older than 72h
            cutoff_72h = now - timedelta(hours=72)
            await db.execute(
                delete(User).where(User.is_verified == False, User.created_at < cutoff_72h)
            )

            await db.commit()

        # 4. Reset proxy failure counters
        proxy_manager.reset_all()

        # 5. Clean stale in-memory rate limit entries
        rate_limiter.cleanup_stale_entries()

        logger.info("CLEANUP_COMPLETE")
```

---

## Configuration

```python
# app/config.py

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EIDOS_", env_file=".env")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    public_domain: str = "eidosspeech.xyz"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/eidosspeech.db"

    # JWT
    secret_key: str = "change-me-in-production-min-64-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Email — Primary SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "eidosSpeech <noreply@eidosspeech.xyz>"

    # Email — Fallback SMTP
    smtp_fallback_host: str = ""
    smtp_fallback_port: int = 587
    smtp_fallback_username: str = ""
    smtp_fallback_password: str = ""

    # Email — Resend API
    resend_api_key: str = ""

    # Turnstile
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    turnstile_enabled: bool = False

    # Rate Limits — Anonymous
    anon_char_limit: int = 500
    anon_req_per_day: int = 5
    anon_req_per_min: int = 1

    # Rate Limits — Registered
    free_char_limit: int = 1000
    free_req_per_day: int = 30
    free_req_per_min: int = 3

    # Proxy
    proxies: str = ""  # comma-separated, empty = no proxy

    # TTS (from v1)
    default_voice: str = "id-ID-GadisNeural"
    max_concurrent: int = 3

    # Cache (from v1)
    cache_dir: str = "./data/cache"
    cache_max_size_gb: float = 5.0
    cache_ttl_days: int = 30

    # AdSense
    adsense_client_id: str = ""
    adsense_slot_top: str = ""
    adsense_slot_below: str = ""

    # Admin
    admin_key: str = "change-me-admin-key"

    def validate_startup(self):
        """Called on app startup — fail loudly if critical config missing"""
        errors = []
        if self.secret_key == "change-me-in-production-min-64-bytes":
            errors.append("EIDOS_SECRET_KEY must be changed from default")
        if not self.smtp_host and not self.resend_api_key:
            errors.append("At least one email provider required (SMTP or Resend)")
        if self.admin_key == "change-me-admin-key":
            errors.append("EIDOS_ADMIN_KEY must be changed from default")
        if errors:
            for e in errors:
                logger.critical(f"CONFIG_ERROR: {e}")
            raise SystemExit(1)
```

---

## Frontend JavaScript Modules

### Module Load Order

```html
<!-- All pages include these in order -->
<script src="/static/js/toast.js"></script>
<script src="/static/js/auth.js"></script>
<script src="/static/js/api-client.js"></script>

<!-- Page-specific -->
<script src="/static/js/audio-player.js"></script>  <!-- TTS App only -->
<script src="/static/js/app.js"></script>            <!-- TTS App only -->
```

### State Flow

```
Page Load
    │
    ▼
AuthStore.init()
    │── hydrate from localStorage
    │── check token expiry
    │── if expired: try refresh
    │── if refresh fails: clearAuth()
    │── update UI (navbar, info banner)
    │
    ▼
ApiClient ready
    │── all requests go through ApiClient
    │── auto-attach Authorization header
    │── auto-refresh on 401
    │
    ▼
App.init() (TTS page only)
    │── fetch voices
    │── populate dropdowns
    │── fetch usage (if authenticated)
    │── update info banner
```

---

## Docker / Deployment

### Volume Mapping

```yaml
# docker-compose.nginx.yml
volumes:
  - app_data:/data          # Contains both cache/ and db/
  # OR separate:
  - tts_cache:/data/cache   # Audio cache
  - app_db:/data/db          # SQLite database
```

### Health Check (v2)

```python
@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    # DB connectivity check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": __version__,
        "db": db_status,
        "cache": cache.stats(),
        "uptime": get_uptime(),
        "proxy": {
            "enabled": bool(settings.proxies),
            "count": len(proxy_manager._proxies) if settings.proxies else 0,
        }
    }
```

### nginx-public.conf

```nginx
server {
    listen 443 ssl http2;
    server_name eidosspeech.xyz;

    ssl_certificate /etc/letsencrypt/live/eidosspeech.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/eidosspeech.xyz/privkey.pem;

    client_max_body_size 1m;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for TTS generation
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # Cache static assets
    location /static/ {
        proxy_pass http://localhost:8000/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Rate limit on auth endpoints (nginx layer)
    location /api/v1/auth/ {
        limit_req zone=auth burst=5 nodelay;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Rate limit zone
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name eidosspeech.xyz;
    return 301 https://$host$request_uri;
}
```

---

## Dependencies

```
# Existing (from v1)
fastapi
uvicorn[standard]
edge-tts>=7.0.0
python-dotenv
pydantic-settings
aiofiles

# New (v2)
sqlalchemy[asyncio]==2.0.x    # Async ORM
aiosqlite==0.20.x             # SQLite async driver
python-jose[cryptography]     # JWT
passlib[bcrypt]               # Password hashing
python-multipart              # Form data
aiosmtplib                    # Async SMTP
httpx                         # HTTP client (Resend API, Turnstile)
```

---

## Edge-TTS Technical Details

### Audio Output
- Format: MP3, 24 kHz, 48 kbps CBR, Mono
- ~6 KB per second of audio

### Voice Stats (v2)
- Base voices: ~310 native + 12 multilingual = 322
- Speechma-style count: **1,200+** (multilingual counted per language)
- Total locales: 142 | Total languages: 75
- 12 multilingual: Andrew, Ava, Brian, Emma, William, Remy, Vivienne, Florian, Seraphina, Giuseppe, Hyunsu, Thalita

### Known Limitations
- Max ~3-5 concurrent WebSocket connections before throttle
- 403 errors recoverable via retry (3 attempts, exponential backoff)
- Output format hardcoded (MP3 48kbps)
