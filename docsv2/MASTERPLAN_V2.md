# eidosSpeech v2 — Public Release Masterplan

## Context

eidosSpeech v2 adalah versi **public** yang completely separate dari v1.

- **v2 = project baru** — beda codebase, beda domain, beda database
- v1 internal (`speech.eidosstack.com`) tetap jalan apa adanya, **gak disentuh**
- User bisa pakai **tanpa register** via Web UI (limited) atau **register** untuk unlock full free tier + API key
- Public version di **domain terpisah** (e.g. `eidosspeech.xyz`)
- eidosSpeech v2 **fully independent** — punya auth, database, admin sendiri
- Hubungan dengan eidosStack = cross-promotion / sponsor only

---

## Business Model

- **Free + Ads** — no paid tier
- Revenue dari **Google AdSense** di TTS App page (bukan landing page)
- Landing page = bersih, profesional, ada **eidosStack ecosystem sponsor banner**
- API user gak lihat ads, tapi limited request/hari
- Email user dikumpulkan untuk marketing eidosStack (consent via ToS saat register)

---

## Tier System (2 Tier Only)

| Feature | Anonymous (No Register) | Registered (Free) |
|---------|:-----------------------:|:------------------:|
| **Web UI** | Yes (+ads) | Yes (+ads) |
| **API access** | **No** (Web UI only) | **Yes** |
| **Karakter/request** | 500 (~70-80 kata ID) | 1.000 (~140-160 kata ID) |
| **Request/hari** | 5 | 30 |
| **Request/menit** | 1 | 3 |
| **Concurrent** | 1 | 1 |
| **Voices** | Semua 1,200+ | Semua 1,200+ |
| **Download MP3** | Yes | Yes |
| **Batch TTS** | No | No |
| **Streaming** | No | No |
| **Auth** | Tidak perlu | Register + email verify |
| **Rate limit by** | IP address | API key + IP |
| **Dashboard** | No | Yes |

> **Note**: Internal use (eidosOne, eidosLumina, dll) tetap pakai v1 di `speech.eidosstack.com`.
> v2 murni public — tidak ada internal tier.

### Anonymous (No Registration)

- Langsung pakai TTS via **Web UI** tanpa register
- Limit: **500 char/request**, **5 request/hari**, **1 request/menit**
- **Tidak bisa** call API external (curl, Python, SDK)
- Web UI internally call `/api/v1/tts`, di-protect via Origin/Referer check
- Rate limit berdasarkan IP address
- Ads tampil di TTS App page
- Info banner: batasan + benefit register

### Registered (Free)

- Register langsung di eidosSpeech (email + password + agree ToS)
- Email verification → auto-generate API key (format: `esk_<random>`)
- Limit: **1.000 char/request**, **30 request/hari**, **3 request/menit**
- API key bisa dipakai di Web UI (otomatis) + API call (header `X-API-Key`)
- Ads tetap tampil di Web UI
- 1 API key per email, bisa regen di dashboard
- Dashboard: usage stats, API key management, quick start guide

---

## Endpoint Access Matrix

| Endpoint | Anonymous (Web UI) | Registered (Free Key) |
|----------|:------------------:|:---------------------:|
| `GET /` | Landing page | Landing page |
| `GET /app` | TTS (5/day, 500ch) | TTS (30/day, 1Kch) |
| `POST /api/v1/tts` | **Web UI only** (Origin check) | Yes |
| `GET /api/v1/voices` | Yes | Yes |
| `GET /api/v1/health` | Yes | Yes |
| `POST /api/v1/auth/*` | Yes | Yes |
| `GET /dashboard` | No | Yes |
| `GET /docs` | Yes (Swagger) | Yes |
| `GET /api-docs` | Yes | Yes |
| `GET /api/v1/admin/*` | No | Admin key only |

**Web UI Only TTS**: Request ke `POST /api/v1/tts` tanpa API key → cek `Origin`/`Referer` header. Dari domain sendiri → allow (IP rate limit). External → 403 "Register for API access".

---

## Frontend Stack

| Concern | Stack | Alasan |
|---------|-------|--------|
| **CSS** | Tailwind CSS (CDN Play) | Utility-first, modern, no build step |
| **Icons** | Lucide Icons (CDN) | Clean modern icons, `<i data-lucide="play">` |
| **Font** | Inter (Google Fonts) | Clean sans-serif, 1 line import |
| **Animation** | CSS transitions/animations | Lightweight, no library |
| **JS** | Vanilla JavaScript | No framework, no bundler |
| **Pages** | Separate HTML files | Landing, app, dashboard, tos, etc. |

Setup = 3 line di `<head>`:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lucide@latest"></script>
```

No build step, no node_modules, no bundler. Static files served langsung oleh FastAPI.

### Design System (contek eidosStack style)

| Token | Value | Notes |
|-------|-------|-------|
| **Theme** | Dark mode only | `bg-gray-950` body, `bg-gray-900` cards |
| **Accent** | Emerald/Green | `text-emerald-500`, `bg-emerald-500/10`, buttons `bg-emerald-600 hover:bg-emerald-700` |
| **Border** | `border-white/10` | Subtle white borders on dark |
| **Radius** | `rounded-2xl` cards, `rounded-lg` inputs/buttons | Consistent rounding |
| **Font sizes** | `text-sm` body, `text-2xl` headings, `text-4xl` hero | Inter weights 400/500/600/700 |
| **Muted text** | `text-gray-400` | Secondary text, labels |
| **Backdrop** | `bg-black/50 backdrop-blur-sm` | Modal overlays |

Tailwind config (inline CDN):
```html
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'sans-serif'] },
      colors: { brand: { DEFAULT: '#10B981', dark: '#059669' } }
    }
  }
}
</script>
```

### Frontend Auth State (contek eidosStack pattern)

Auth state di-manage via vanilla JS module — simplified dari eidosStack Zustand pattern:

```javascript
// app/static/js/auth.js — Auth state manager
const AuthStore = {
    _state: 'UNAUTHENTICATED',  // UNAUTHENTICATED | AUTHENTICATED | SESSION_EXPIRED
    _token: null,                // Access token (JWT)
    _refreshToken: null,         // Refresh token
    _user: null,                 // { email, full_name, is_verified }
    _apiKey: null,               // esk_xxx

    init() {
        // Hydrate dari localStorage on page load
        const stored = localStorage.getItem('eidosspeech_auth');
        if (stored) { Object.assign(this, JSON.parse(stored)); }
        this._evaluateSession();
    },

    setAuth(token, refreshToken, user, apiKey) { ... },
    clearAuth() { ... },
    getToken() { return this._token; },
    isAuthenticated() { return this._state === 'AUTHENTICATED'; },

    _persist() {
        localStorage.setItem('eidosspeech_auth', JSON.stringify({
            _state: this._state, _token: this._token,
            _refreshToken: this._refreshToken, _user: this._user, _apiKey: this._apiKey
        }));
    },

    async _evaluateSession() {
        // Check token expiry, auto-refresh if needed
        // Called on init + every 60 seconds
    }
};
```

### Frontend API Client (contek eidosStack pattern)

```javascript
// app/static/js/api-client.js — HTTP client with auto-refresh
const ApiClient = {
    async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };

        // Attach auth header if logged in
        const token = AuthStore.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        let response = await fetch(`/api/v1${path}`, { method, headers, body: body ? JSON.stringify(body) : null });

        // Auto-refresh on 401 (contek eidosStack pattern)
        if (response.status === 401 && token && !path.includes('/auth/')) {
            const refreshed = await this._refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${AuthStore.getToken()}`;
                response = await fetch(`/api/v1${path}`, { method, headers, body: body ? JSON.stringify(body) : null });
            } else {
                AuthStore.clearAuth();
                showToast('Session expired. Please login again.', 'error');
            }
        }

        return response;
    },

    async _refreshToken() { ... },

    // Convenience methods
    get: (path) => ApiClient.request('GET', path),
    post: (path, body) => ApiClient.request('POST', path, body),
};
```

### Toast Notification System

Vanilla JS toast — simple, no library:

```javascript
// app/static/js/toast.js
function showToast(message, type = 'info', duration = 5000) {
    // type: 'success' | 'error' | 'info' | 'warning'
    // Colors: success=emerald, error=red, info=blue, warning=amber
    // Auto-dismiss after duration
    // Position: top-right (fixed)
    // Animation: slide-in from right, fade-out
}
```

Semua page include `toast.js`. Dipakai untuk:
- Auth success/error ("Logged in!", "Invalid password")
- TTS generate success/error
- Copy to clipboard feedback ("API key copied!")
- Rate limit warnings ("Daily limit reached")

---

## Infrastructure

### Email Service (contek eidosStack multi-provider pattern)

eidosStack pakai **fallback chain** (Brevo → Mailtrap → Resend → SES). eidosSpeech v2 contek pattern yang sama — multi-provider dengan fallback:

```
Fallback order: Primary SMTP → Fallback SMTP → Resend API
```

```python
# app/services/email_service.py
class EmailDispatcher:
    """
    Multi-provider email dengan fallback chain.
    Contek eidosStack EmailDispatcher pattern — non-blocking, best-effort.
    """
    providers: list[EmailProvider]  # ordered by priority

    async def send(self, to: str, subject: str, html: str, critical: bool = False) -> bool:
        for provider in self.providers:
            try:
                await provider.send(to, subject, html)
                return True
            except Exception as e:
                logger.warning(f"Email provider {provider.name} failed: {e}")
                continue

        # All providers failed
        if critical:
            raise EmailDeliveryError("All email providers failed")
        logger.error(f"All email providers failed for {to}")
        return False  # non-blocking — registration still proceeds
```

**Providers:**

| Provider | Type | Config | Notes |
|----------|------|--------|-------|
| Primary SMTP | SMTP (nodemailer-style) | `EIDOS_SMTP_*` env vars | Brevo, Mailtrap, any SMTP |
| Fallback SMTP | SMTP | `EIDOS_SMTP_FALLBACK_*` env vars | Second SMTP provider |
| Resend API | REST API | `EIDOS_RESEND_API_KEY` | HTTP fallback, no SMTP needed |

**Non-blocking pattern** (contek eidosStack ADR-005):
- Email send = **best-effort, non-critical** by default
- Registration proceeds even if email fails → user can resend verification
- Failure logged but **never blocks** user operations
- `critical=True` only for password reset (must succeed)

**Email templates** (inline HTML, same pattern as eidosStack):

| Email | Subject | Content |
|-------|---------|---------|
| Verification | "Verify your eidosSpeech account" | Link to `/verify-email?token=xxx`, expires 24h, brand header |
| Password Reset | "Reset your eidosSpeech password" | Link to `/reset-password?token=xxx`, expires 1h, IP address warning |
| Welcome | "Welcome to eidosSpeech!" | API key, quick start, dashboard link |

Token format: `secrets.token_urlsafe(32)` — 256-bit cryptographically secure.

### Proxy (Optional, Built-in dari Awal)

Proxy **built-in ke core** tapi sifatnya **optional config**:
- `EIDOS_PROXIES=` (kosong) → direct connection, no proxy
- `EIDOS_PROXIES=http://proxy1,http://proxy2,...` → round-robin aktif
- Tinggal isi env var, restart, done

Webshare free proxy (10-20 proxy) sudah lebih dari cukup.
Round-robin dengan failure tracking — kalau proxy gagal 3x, skip, fallback ke direct.

```python
class ProxyManager:
    def __init__(self, proxies: list[str]):
        self._proxies = proxies
        self._cycle = itertools.cycle(proxies)
        self._failures: dict[str, int] = {}

    async def get_next(self) -> str | None:
        if not self._proxies:
            return None  # direct connection
        # Skip proxies with 3+ consecutive failures
        # Return None if all failed (fallback to direct)

    async def mark_failure(self, proxy: str): ...
    async def mark_success(self, proxy: str): ...
```

---

### CORS Policy

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"https://{settings.public_domain}",   # eidosspeech.xyz
        "http://localhost:8000",                 # dev
        "http://localhost:3000",                 # dev frontend
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Admin-Key"],
    expose_headers=[
        "X-RateLimit-Tier", "X-RateLimit-Limit-Day", "X-RateLimit-Remaining-Day",
        "X-RateLimit-Limit-Min", "X-RateLimit-Char-Limit",
        "X-Cache-Hit", "X-Cache-Key", "Retry-After"
    ],
)
```

Note: Origin check di `resolve_request_context` is **separate** dari CORS — CORS = browser security, Origin check = tier detection logic.

### Error Response Format

Consistent JSON error format (extend v1 pattern):

```json
{
    "error": "RateLimitError",
    "message": "Daily request limit exceeded. Register for 30 requests/day.",
    "detail": {
        "tier": "anonymous",
        "limit": 5,
        "reset_at": "2024-01-16T00:00:00Z"
    }
}
```

| HTTP Code | Error Type | When |
|-----------|-----------|------|
| 400 | `ValidationError` | Invalid input (bad email, short password, empty text) |
| 401 | `AuthenticationError` | Invalid/expired JWT, bad credentials |
| 403 | `ForbiddenError` | No API key + external origin, banned user, disabled key |
| 404 | `NotFoundError` | Voice not found, user not found |
| 409 | `ConflictError` | Email already registered |
| 422 | `UnprocessableEntity` | Text too long for tier, invalid voice ID |
| 429 | `RateLimitError` | Per-minute, per-day, or concurrent limit hit |
| 500 | `InternalError` | TTS engine failure, DB error (no internals exposed) |
| 503 | `ServiceUnavailable` | All proxies + direct failed |

Rate limit 429 response **must include**:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Tier: anonymous
X-RateLimit-Limit-Day: 5
X-RateLimit-Remaining-Day: 0
```

### Rate Limit Response Headers

Setiap TTS response include headers ini:

```
X-RateLimit-Tier: anonymous|registered
X-RateLimit-Limit-Day: 5|30
X-RateLimit-Remaining-Day: 3
X-RateLimit-Limit-Min: 1|3
X-RateLimit-Char-Limit: 500|1000
X-Cache-Hit: true|false
X-Cache-Key: <sha256>
```

Daily reset: **UTC midnight** (00:00 UTC). Simple, no timezone complexity.

### Logging Strategy

Structured logging — extend v1 pattern with auth/security events:

```python
# Log levels:
# INFO  — normal operations (TTS request, register, login)
# WARNING — rate limit hit, proxy failure, email send failure
# ERROR — all providers failed, DB error, unexpected exception
# DEBUG — request context resolution, cache hit/miss, proxy selection

# Security-relevant logs (audit trail):
logger.info(f"USER_REGISTER email={email} ip={ip}")
logger.info(f"USER_VERIFY email={email}")
logger.info(f"USER_LOGIN email={email} ip={ip}")
logger.info(f"USER_LOGOUT email={email} jti={jti}")
logger.warning(f"AUTH_FAIL email={email} ip={ip} reason={reason}")
logger.warning(f"RATE_LIMIT tier={tier} ip={ip} limit_type={type}")
logger.info(f"API_KEY_REGEN user_id={user_id}")
logger.info(f"ADMIN_ACTION action={action} target={target}")
```

Log rotation: handled by Docker logging driver (default `json-file` with max-size). No app-level rotation needed.

### Periodic Cleanup Tasks

Background tasks di `app/main.py` lifespan:

```python
async def periodic_cleanup():
    """Run every 1 hour"""
    while True:
        await asyncio.sleep(3600)
        # 1. Clean expired token revocations (older than 7 days)
        # 2. Clean old registration_attempts (older than 7 days)
        # 3. Clean stale in-memory rate limit entries
        # 4. Reset proxy failure counters
```

---

## Cross-Promotion / Sponsor Strategy

1. **Landing page**: "Part of eidosStack ecosystem" sponsor banner (no AdSense)
2. **TTS App page**: eidosStack ecosystem banner di bawah + footer "Powered by eidosStack"
3. **Footer (semua page)**: "Powered by eidosStack" + link ke eidosstack.com
4. **"More Tools" section**: List produk eidosStack (eidosOne, eidosLumina, etc.)
5. **SEO**: Rank untuk "free TTS Indonesia", "text to speech API gratis" → traffic magnet

---

## User Flow

### Flow Tanpa Register
```
eidosspeech.xyz (Landing Page)
    │
    ├── "Try Now" → /app (TTS Tool)
    │                 ├── Langsung generate (5x/hari, 500 char)
    │                 ├── Info banner: batasan + benefit register
    │                 ├── Gabisa panggil API external
    │                 └── Limit habis → modal register
    │
    └── "Get Free API Key" → /app#register (auto open register modal)
```

### Flow Register
```
Register (email + password + agree ToS)
    → Email verification link (expire 24h)
    → Click verify → auto-generate API key (esk_<random>)
    → Redirect ke /app (logged in, 30/day, 1000 char, API access)
```

---

## Page Structure

### Routes

| Route | Description |
|-------|-------------|
| `/` | Landing page |
| `/app` | TTS tool (main app) |
| `/app#register` | TTS tool + auto open register modal |
| `/dashboard` | User dashboard (usage stats, API key, regen key) |
| `/verify-email?token=xxx` | Email verification redirect |
| `/reset-password?token=xxx` | Password reset page |
| `/tos` | Terms of Service (include email marketing consent) |
| `/docs` | API documentation (FastAPI Swagger UI) |
| `/api-docs` | Custom API docs (curl/Python/JS examples) |
| `/admin` | Admin panel (admin key required) |

### Landing Page Layout (`/`)

```
┌──────────────────────────────────────────────────┐
│ [Logo] eidosSpeech            [Try Now] [Get API Key] │
├──────────────────────────────────────────────────┤
│                                                        │
│   Free Text-to-Speech API                              │
│   1,200+ AI Voices · 75+ Languages                     │
│                                                        │
│   [ Try Now - No Registration Required ]               │
│                                                        │
├──────────────────────────────────────────────────┤
│   ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│   │ 1,200+   │  │ 75+      │  │ Free     │           │
│   │ Voices   │  │ Languages│  │ API      │           │
│   └──────────┘  └──────────┘  └──────────┘           │
├──────────────────────────────────────────────────┤
│   Live Demo (embedded mini player)                     │
│   ┌──────────────────────────────────┐                │
│   │ "Halo, selamat datang di..."     │  ▶ Play        │
│   │ Voice: Gadis (Indonesian)        │                │
│   └──────────────────────────────────┘                │
├──────────────────────────────────────────────────┤
│   API Code Snippet                                     │
│   ┌──────────────────────────────────┐                │
│   │ curl -X POST .../api/v1/tts     │  [Copy]        │
│   │   -H "X-API-Key: YOUR_KEY"      │                │
│   │   -d '{"text":"Hello"}'         │                │
│   └──────────────────────────────────┘                │
├──────────────────────────────────────────────────┤
│   ┌─ eidosStack Ecosystem Sponsor ──────────────┐     │
│   │  Part of the eidosStack ecosystem            │     │
│   │  eidosOne · eidosLumina · and more           │     │
│   │  [Explore eidosstack.com →]                  │     │
│   └──────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────┤
│   Powered by eidosStack · Terms of Service             │
└──────────────────────────────────────────────────┘
```

**No AdSense di landing page** — bersih, profesional, fokus convert.

### TTS App Page Layout (`/app`)

```
┌──────────────────────────────────────────────────┐
│ [Logo] eidosSpeech             [Login] [Register]      │
├──────────────────────────────────────────────────┤
│ ┌─ Info Banner (anonymous) ─────────────────────┐      │
│ │ You have 4/5 free requests today (500 chars)   │      │
│ │ Register FREE to unlock: 30 req/day, 1000      │      │
│ │ chars, API access  [Register →]                │      │
│ └────────────────────────────────────────────────┘      │
├──────────────────────────────────────────────────┤
│ [AdSense Banner 728x90]                                │
├──────────────────────────────────────────────────┤
│                                                        │
│  ┌─ Text Input ──────┐  ┌─ Voice + Controls ────┐     │
│  │                    │  │ Language: [Indonesian]  │     │
│  │                    │  │ Gender: [All] [M] [F]  │     │
│  │                    │  │ Voice: [Gadis]          │     │
│  │                    │  │ Rate: ──●──             │     │
│  │          0/500 cha │  │ Pitch: ──●──            │     │
│  └────────────────────┘  │ [▶ Generate]            │     │
│                          └─────────────────────────┘     │
│                                                        │
│  ┌─ Audio Player ──────────────────────────────┐       │
│  │  ▶  ───●──────  01:23 / 02:45  [Download]  │       │
│  └─────────────────────────────────────────────┘       │
│                                                        │
│  [AdSense Rectangle 300x250]                           │
│                                                        │
│  ┌─ eidosStack Ecosystem Banner ──────────────┐        │
│  │  Part of eidosStack ecosystem               │        │
│  │  eidosOne · eidosLumina · More →            │        │
│  └─────────────────────────────────────────────┘        │
│                                                        │
│  Powered by eidosStack · Terms · API Docs              │
└──────────────────────────────────────────────────┘
```

### Info Banner States

**Anonymous (not logged in):**
```
┌────────────────────────────────────────────────┐
│ ⚡ You have 4/5 free requests today (500 chars) │
│ Register FREE: 30 req/day · 1000 chars · API   │
│ access  [Register Now →]                        │
└────────────────────────────────────────────────┘
```

**Registered (logged in):**
```
┌────────────────────────────────────────────────┐
│ ⚡ 28/30 requests remaining · 1000 chars/req    │
│ API Key: esk_••••••••abcd  [Copy] [Dashboard]  │
└────────────────────────────────────────────────┘
```

**Limit habis (anonymous):**
```
┌─────────────────────────────────────┐
│  Daily limit reached                 │
│                                      │
│  You've used 5/5 free requests       │
│  today.                              │
│                                      │
│  Register for FREE to unlock:        │
│  ✓ 30 requests/day                  │
│  ✓ 1000 characters/request          │
│  ✓ Personal API key                 │
│  ✓ API access (curl, Python, etc.)  │
│                                      │
│  [Register Now]  [Maybe Later]       │
└─────────────────────────────────────┘
```

### User Dashboard (`/dashboard`)

```
┌──────────────────────────────────────────────────┐
│ [Logo] eidosSpeech         [Back to App] [Logout]      │
├──────────────────────────────────────────────────┤
│                                                        │
│  ┌─ Today's Usage ─────────────────────────────┐       │
│  │  Requests: 12/30  ████████░░░░░  (40%)      │       │
│  │  Characters: 4,521 used today               │       │
│  └─────────────────────────────────────────────┘       │
│                                                        │
│  ┌─ Your API Key ──────────────────────────────┐       │
│  │  esk_a1b2c3d4e5f6g7h8i9j0                  │       │
│  │  [Copy]  [Regenerate Key]                   │       │
│  └─────────────────────────────────────────────┘       │
│                                                        │
│  ┌─ Your Limits ───────────────────────────────┐       │
│  │  Tier: Free                                  │       │
│  │  Max chars/request: 1000                     │       │
│  │  Max requests/day: 30                        │       │
│  │  Max requests/min: 3                         │       │
│  │  API access: Yes                             │       │
│  └─────────────────────────────────────────────┘       │
│                                                        │
│  ┌─ Quick Start ───────────────────────────────┐       │
│  │  curl -X POST https://eidosspeech.xyz/...   │       │
│  │  [See full API docs →]                      │       │
│  └─────────────────────────────────────────────┘       │
│                                                        │
│  Powered by eidosStack · Terms · API Docs              │
└──────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Database + Auth + Rate Limit + Proxy
> Core backend — semua fundamental.

**Database: SQLite + SQLAlchemy async**

**Database schema:**

```sql
-- Users
users:
  id                    INTEGER PRIMARY KEY
  email                 VARCHAR(255) UNIQUE NOT NULL
  password_hash         VARCHAR(255) NOT NULL
  full_name             VARCHAR(255)
  is_verified           BOOLEAN DEFAULT FALSE
  is_active             BOOLEAN DEFAULT TRUE
  tos_accepted_at       DATETIME NOT NULL
  verification_token    VARCHAR(64) UNIQUE
  verification_expires  DATETIME
  reset_token           VARCHAR(64) UNIQUE
  reset_token_expires   DATETIME
  last_login_at         DATETIME
  created_at            DATETIME DEFAULT NOW
  updated_at            DATETIME DEFAULT NOW

-- API Keys
api_keys:
  id            INTEGER PRIMARY KEY
  key           VARCHAR(64) UNIQUE NOT NULL         -- format: esk_<random>
  user_id       INTEGER FK -> users.id
  is_active     BOOLEAN DEFAULT TRUE
  created_at    DATETIME DEFAULT NOW
  last_used_at  DATETIME

-- Daily Usage Tracking
daily_usage:
  id            INTEGER PRIMARY KEY
  api_key_id    INTEGER FK -> api_keys.id (nullable)
  ip_address    VARCHAR(45) (nullable)
  date          DATE NOT NULL
  request_count INTEGER DEFAULT 0
  chars_used    INTEGER DEFAULT 0

-- Token Revocation
token_revocations:
  jti           VARCHAR(64) PRIMARY KEY
  expires_at    DATETIME NOT NULL

-- Registration Rate Limit
registration_attempts:
  id            INTEGER PRIMARY KEY
  ip_address    VARCHAR(45) NOT NULL
  date          DATE NOT NULL
  attempt_count INTEGER DEFAULT 0
```

**Auth Pattern (contek eidosStack):**
- Password: bcrypt salt 10, **min 8 char, max 128 char** (no complexity requirement — length > complexity)
- JWT: HS256, token type field (`access`, `refresh`, `verify`, `reset`)
- Access token: 15 menit, Refresh token: 7 hari
- Token revocation via JTI
- Turnstile CAPTCHA on login (optional, `EIDOS_TURNSTILE_ENABLED`)
- Return token di JSON body (frontend reads from response, stores in localStorage)
- API key format: `esk_` + `secrets.token_urlsafe(24)` = 36 char total, 192-bit entropy
- API key regen cooldown: 1x per 5 menit (prevent abuse)

**Auth endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Email + password + agree ToS → create user, send verification email |
| POST | `/api/v1/auth/verify-email` | Token → verify, auto-generate API key |
| POST | `/api/v1/auth/login` | Email + password + Turnstile → access + refresh token |
| POST | `/api/v1/auth/refresh` | Refresh token → new token pair |
| POST | `/api/v1/auth/logout` | Revoke token via JTI |
| GET | `/api/v1/auth/me` | Profile + API key + usage stats |
| POST | `/api/v1/auth/forgot-password` | Send reset email |
| POST | `/api/v1/auth/reset-password` | Token + new password |
| POST | `/api/v1/auth/resend-verification` | Rate limited 1 per 5 min |
| POST | `/api/v1/auth/regen-key` | Regenerate API key |

**Core: `resolve_request_context`**

```
RequestContext:
  tier: "anonymous" | "registered"
  api_key: str | None
  api_key_id: int | None
  user_id: int | None
  ip_address: str
  char_limit: int
  req_per_day: int
  req_per_min: int
  is_web_ui: bool
```

Resolution:
1. `X-API-Key` header → lookup DB → "registered"
2. `Authorization: Bearer <jwt>` → decode → load API key → "registered"
3. No key/token + Origin = own domain → "anonymous" (IP limit)
4. No key/token + external Origin → 403

**Rate Limiting: In-memory + SQLite (No Redis)**
- Per-minute: in-memory sliding window (`deque` of timestamps per identity)
- Per-day: `daily_usage` table in SQLite (persistent across restarts)
- Concurrent: `asyncio.Semaphore(1)` per identity — reject (not queue) if already processing
- IP rate limit always on (even with API key)
- Daily reset: **UTC midnight** — `daily_usage.date` column, new row per day
- Identity = IP (anonymous) or API key ID (registered)
- No Redis needed — SQLite WAL handles concurrent reads, in-memory handles per-minute
- Response headers: `X-RateLimit-Tier`, `X-RateLimit-Remaining-Day`, etc. (see Infrastructure section)

**Proxy: Optional, built-in**
- `EIDOS_PROXIES=` empty → direct, no proxy
- `EIDOS_PROXIES=http://p1,http://p2` → round-robin active
- Failure tracking, fallback to direct

**New files:**

| File | Purpose |
|------|---------|
| `app/db/__init__.py` | Package marker |
| `app/db/database.py` | SQLAlchemy async engine, session factory, WAL mode |
| `app/db/models.py` | ORM models (5 tables) |
| `app/db/seed.py` | Init DB on startup |
| `app/core/jwt_handler.py` | JWT create/decode, token types |
| `app/core/rate_limiter.py` | Hybrid rate limiter |
| `app/api/v1/auth.py` | Auth endpoints |
| `app/services/email_service.py` | Multi-provider email (SMTP + Resend API fallback) |
| `app/services/proxy_manager.py` | Round-robin proxy |

**Modified files:**

| File | Changes |
|------|---------|
| `app/config.py` | 20+ new settings |
| `app/core/auth.py` | Replace with `resolve_request_context` |
| `app/core/exceptions.py` | Add `RateLimitError` |
| `app/models/schemas.py` | Auth schemas, remove text max_length |
| `app/api/v1/__init__.py` | Register auth router |
| `app/__init__.py` | Version bump `"1.0.0"` → `"2.0.0"` |
| `app/api/v1/tts.py` | Wire RequestContext + rate limiter + Origin check |
| `app/api/v1/batch.py` | Return 410 Gone ("Batch TTS is not available in v2") |
| `app/api/v1/health.py` | Add DB connectivity check to health response |
| `app/main.py` | DB init, cleanup tasks, page routes |
| `app/services/tts_engine.py` | Proxy parameter |
| `requirements.txt` | 6 new deps |
| `.env.example` | All new env vars |
| `Dockerfile` | `/data/db` directory |
| `docker-compose.nginx.yml` | `app_data` volume |

---

### Phase 2: Frontend — Landing + App + Dashboard
> Depends: Phase 1

**Frontend stack:** Tailwind CSS (CDN) + Lucide Icons + Inter font + Vanilla JS

**New files:**

| File | Purpose |
|------|---------|
| `app/static/landing.html` | Landing page (Tailwind) |
| `app/static/dashboard.html` | User dashboard (Tailwind) |
| `app/static/tos.html` | Terms of Service |
| `app/static/verify-email.html` | Email verification page |
| `app/static/reset-password.html` | Password reset page |
| `app/static/api-docs.html` | Custom API docs |

**Modified files:**

| File | Changes |
|------|---------|
| `app/static/index.html` | Rewrite ke Tailwind, auth modal, info banner, AdSense slots |
| `app/static/js/app.js` | Auth state, info banner, usage display, char limit |
| `app/static/js/api-client.js` | Auth methods, JWT/cookie handling |
| `app/static/css/style.css` | Minimal custom CSS (Tailwind handles most) |
| `app/main.py` | Page routes (`/` → landing, `/app` → index, `/dashboard`, etc.) |

---

### Phase 3: Admin + Deploy
> Depends: Phase 1-2

**New files:**

| File | Purpose |
|------|---------|
| `app/api/v1/admin.py` | Admin API (stats, users, usage, ban, blacklist) |
| `app/static/admin.html` | Admin dashboard UI (Tailwind, dark theme) |
| `nginx-public.conf` | nginx config untuk public domain |

**Admin auth**: Header `X-Admin-Key` — static key dari `EIDOS_ADMIN_KEY` env var.
Simple, no session/token — admin panel hanya buat owner.

**Admin endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/stats` | Total users, API keys, requests today, cache |
| GET | `/api/v1/admin/users` | Paginated user list |
| GET | `/api/v1/admin/usage` | Daily aggregates (last N days) |
| GET | `/api/v1/admin/usage/voices` | Popular voices/languages |
| POST | `/api/v1/admin/keys/{id}/disable` | Disable API key |
| POST | `/api/v1/admin/users/{id}/ban` | Ban user (set `is_active=false`) |
| POST | `/api/v1/admin/blacklist` | Blacklist IP/email (permanent block) |

**Admin dashboard UI** (contek eidosStack sidebar style):
- Dark theme, card-based layout
- Sidebar: Stats, Users, Usage, Blacklist
- Stats: total users, verified, API keys active, requests today, cache hit rate
- Users: table with email, verified status, API key, usage, ban button
- Usage: daily chart (last 30 days), popular voices/languages

---

## Abuse Protection

| Protection | Implementation |
|------------|---------------|
| 1 API key per email | Enforce di registration |
| Max 3 register per IP per day | `registration_attempts` table |
| Same email = blocked regardless of IP | UNIQUE constraint on `users.email` |
| Rate limit per IP (always on) | Even with API key |
| Concurrent = 1 per identity | Reject (429), not queue |
| Turnstile CAPTCHA | On login form (when enabled) |
| Email verification | Required untuk API key |
| Blacklist IP/email | Admin endpoint (permanent) |
| Token revocation | Logout invalidates via JTI |
| Password min 8, max 128 char | Validation di register + reset |
| Unverified cleanup | Users not verified within 72h → auto-delete (cleanup task) |
| Failed login tracking | Log IP + email on auth failure (for admin review, not auto-ban) |

---

## File Change Summary

### New Files (19)
```
app/db/__init__.py
app/db/database.py
app/db/models.py
app/db/seed.py
app/core/rate_limiter.py
app/core/jwt_handler.py
app/api/v1/auth.py
app/api/v1/admin.py
app/services/email_service.py
app/services/proxy_manager.py
app/static/landing.html
app/static/dashboard.html
app/static/tos.html
app/static/verify-email.html
app/static/reset-password.html
app/static/api-docs.html
app/static/admin.html
app/static/js/auth.js          ← NEW: auth state manager
app/static/js/toast.js         ← NEW: toast notification system
nginx-public.conf
```

### Modified Files (16+)
```
app/__init__.py             — version "1.0.0" → "2.0.0"
app/config.py               — 20+ new settings, startup validation
app/core/auth.py            — replace with resolve_request_context
app/core/exceptions.py      — add RateLimitError, AuthError, ConflictError
app/models/schemas.py       — auth schemas, remove text max_length
app/api/v1/__init__.py      — register auth + admin routers
app/api/v1/tts.py           — RequestContext + rate limiter + Origin check
app/api/v1/batch.py         — return 410 Gone (batch = v1 only)
app/api/v1/health.py        — add DB connectivity check
app/main.py                 — DB init, page routes, admin, cleanup tasks, CORS
app/services/tts_engine.py  — proxy parameter
app/static/index.html       — rewrite Tailwind dark theme, auth modal, info banner, ads
app/static/js/app.js        — auth state integration, usage display, char limit
app/static/js/api-client.js — auth methods, JWT handling, auto-refresh on 401
app/static/css/style.css    — minimal custom CSS (Tailwind handles most)
requirements.txt            — new deps
.env.example                — all new env vars (multi-provider SMTP)
Dockerfile                  — /data/db directory
docker-compose.nginx.yml    — app_data volume
```

### Unchanged Files
```
app/core/cache.py            — cache logic tetap
app/services/voice_service.py — voice listing tetap
app/services/batch_service.py — tetap (not used in v2, batch.py returns 410)
app/api/v1/voices.py         — tetap public
app/static/js/audio-player.js — audio player tetap
nginx.conf                    — Docker internal tetap
```

---

## Execution Order

```
Phase 1 (DB + Auth + Rate Limit + Proxy)
    ↓
Phase 2 (Frontend: Landing + App + Dashboard)
    ↓
Phase 3 (Admin + Deploy)
```

3 phase. Simple. Linear.

---

## New Dependencies

```
sqlalchemy[asyncio]==2.0.x    # Async ORM
aiosqlite==0.20.x             # SQLite async driver
python-jose[cryptography]     # JWT handling
passlib[bcrypt]               # Password hashing
python-multipart              # Form data parsing
aiosmtplib                    # Async SMTP (multi-provider, replaces fastapi-mail)
httpx                         # Async HTTP client (for Resend API fallback + Turnstile verify)
```

Note: `fastapi-mail` diganti `aiosmtplib` + `httpx` — lebih flexible buat multi-provider pattern. `aiosmtplib` = raw SMTP async, `httpx` = REST API calls (Resend, Turnstile).

---

## Environment Variables (New)

```env
# Database
EIDOS_DATABASE_URL=sqlite+aiosqlite:///./data/eidosspeech.db

# JWT / Auth
EIDOS_SECRET_KEY=change-me-in-production-min-64-bytes
EIDOS_JWT_ALGORITHM=HS256
EIDOS_ACCESS_TOKEN_EXPIRE_MINUTES=15
EIDOS_REFRESH_TOKEN_EXPIRE_DAYS=7

# Email — Primary SMTP (contek eidosStack multi-provider pattern)
EIDOS_SMTP_HOST=smtp-relay.brevo.com
EIDOS_SMTP_PORT=587
EIDOS_SMTP_USERNAME=
EIDOS_SMTP_PASSWORD=
EIDOS_SMTP_FROM=eidosSpeech <noreply@eidosspeech.xyz>

# Email — Fallback SMTP (optional, second provider)
EIDOS_SMTP_FALLBACK_HOST=
EIDOS_SMTP_FALLBACK_PORT=587
EIDOS_SMTP_FALLBACK_USERNAME=
EIDOS_SMTP_FALLBACK_PASSWORD=

# Email — Resend API fallback (optional, REST-based)
EIDOS_RESEND_API_KEY=

# Cloudflare Turnstile (optional)
EIDOS_TURNSTILE_SITE_KEY=
EIDOS_TURNSTILE_SECRET_KEY=
EIDOS_TURNSTILE_ENABLED=false

# Rate Limits — Anonymous (Web UI only)
EIDOS_ANON_CHAR_LIMIT=500
EIDOS_ANON_REQ_PER_DAY=5
EIDOS_ANON_REQ_PER_MIN=1

# Rate Limits — Registered (Free)
EIDOS_FREE_CHAR_LIMIT=1000
EIDOS_FREE_REQ_PER_DAY=30
EIDOS_FREE_REQ_PER_MIN=3

# Proxy (comma-separated, optional — kosong = no proxy)
EIDOS_PROXIES=

# Google AdSense
EIDOS_ADSENSE_CLIENT_ID=ca-pub-xxxxxxxxx
EIDOS_ADSENSE_SLOT_TOP=1234567890
EIDOS_ADSENSE_SLOT_BELOW=0987654321

# Domain
EIDOS_PUBLIC_DOMAIN=eidosspeech.xyz

# Admin
EIDOS_ADMIN_KEY=change-me-admin-key
```

**Startup validation**: App checks `EIDOS_SECRET_KEY` is not default value dan at least 1 email provider configured (primary SMTP atau Resend). Fail loudly kalau gak valid.

---

## Verification Checklist

1. **Landing page**: `eidosspeech.xyz` → landing page, dark theme, no AdSense, eidosStack sponsor
2. **Try Now**: "Try Now" → `/app`, generate tanpa register (5x/hari, 500 char)
3. **Info banner**: Anonymous → batasan + benefit register. Registered → usage + API key
4. **Limit habis**: Request ke-6 → modal register + benefit list
5. **API block**: `curl POST /api/v1/tts` tanpa key → 403 "Register for API access"
6. **Register**: Register + ToS → email verify → auto API key
7. **Email fallback**: Primary SMTP down → fallback SMTP → Resend API → log error, user can resend
8. **Login**: Login + Turnstile → access (15m) + refresh (7d) token
9. **Token refresh**: Access expired → auto-refresh via refresh token → seamless UX
10. **API call**: `curl -H "X-API-Key: esk_xxx" POST /api/v1/tts` → 30/day, 1000 char
11. **Dashboard**: `/dashboard` → usage stats, API key, regen, limits, quick start
12. **Forgot password**: Reset email → new password → all sessions invalidated
13. **Rate limit headers**: `X-RateLimit-*` headers + `Retry-After` di 429 response
14. **Concurrent reject**: 2 simultaneous requests → second gets 429
15. **Batch endpoint**: `POST /api/v1/batch/tts` → 410 Gone
16. **Health check**: `/api/v1/health` → includes DB connectivity status
17. **Admin**: `GET /api/v1/admin/stats` + `X-Admin-Key` header → stats
18. **Ads**: TTS App → AdSense. Landing page → no ads
19. **Toast notifications**: Success/error/warning messages visible to user
20. **Abuse**: 3 register/IP/day, 1 key/email, IP limit always on
21. **Proxy**: `EIDOS_PROXIES` kosong → direct. Diisi → round-robin
22. **Startup validation**: Missing `SECRET_KEY` or no email provider → fail loudly
23. **Cleanup tasks**: Expired tokens, old registration attempts, unverified users → auto-cleaned
24. **Docker**: `docker compose up` → SQLite persistent, all working
25. **Version**: `app/__init__.py` → `"2.0.0"`

---

## Voices

**Total: 1,200+ voices** (Speechma-style counting)

- ~310 native voices (language-specific)
- 12 multilingual voices (work with all languages)
- Speechma-style: native + (multilingual × supported languages) = 1,200+
- Same engine as v1 — `edge-tts` (Microsoft Azure Neural TTS)

---

## Cost Estimate

### Launch ($0/bulan)

| Item | Cost |
|------|------|
| edge-tts | $0 |
| Webshare free proxy (10-20) | $0 |
| VPS (existing) | $0 |
| Domain (subdomain) | $0 |
| SMTP (Resend free, 100 emails/day) | $0 |
| Turnstile | $0 |
| **Total** | **$0** |

### Scale Up

| Item | Cost/bulan |
|------|-----------|
| Webshare paid 100 proxy | $4 |
| Dedicated domain | ~$1 |
| SMTP upgrade | ~$20 |
| AdSense revenue | +$?? |
