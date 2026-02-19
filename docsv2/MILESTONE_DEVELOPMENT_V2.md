# eidosSpeech v2 — Development Milestones

> Semua milestone mengacu ke [MASTERPLAN_V2.md](./MASTERPLAN_V2.md) dan [TECHNICAL_SPEC_V2.md](./TECHNICAL_SPEC_V2.md)
> v1 milestones: [../docs/MILESTONE_DEVELOPMENT.md](../docs/MILESTONE_DEVELOPMENT.md)

---

## Overview

> **Development Status** — Started: 2026-02-20 | Last Updated: 2026-02-20
>
> | Status | Emoji |
> |--------|-------|
> | Not Started | ⬜ |
> | In Progress | 🔄 |
> | Completed | ✅ |

| Milestone | Scope | Phase | Depends On | Status |
|-----------|-------|-------|------------|--------|
| **M1** | Database + Config | Phase 1 | — | ✅ |
| **M2** | Auth System | Phase 1 | M1 | ✅ |
| **M3** | Email Service | Phase 1 | M1 | ✅ |
| **M4** | Rate Limiting + Request Context | Phase 1 | M1, M2 | ✅ |
| **M5** | Proxy Manager + TTS Wiring | Phase 1 | M1, M4 | ✅ |
| **M6** | Landing Page | Phase 2 | M2 | ✅ |
| **M7** | TTS App Rewrite | Phase 2 | M4, M5 | ✅ |
| **M8** | User Dashboard + Static Pages | Phase 2 | M2, M7 | ✅ |
| **M9** | Admin Panel | Phase 3 | M4, M8 | ✅ |
| **M10** | Deploy + Polish | Phase 3 | M1-M9 | ✅ |

```
M1 (DB + Config)
 ├── M2 (Auth)
 │    ├── M3 (Email)
 │    └── M4 (Rate Limit + Context)
 │         ├── M5 (Proxy + TTS Wiring)
 │         │    └── M7 (TTS App Rewrite)
 │         │         └── M8 (Dashboard + Static)
 │         │              └── M9 (Admin)
 │         └── M6 (Landing Page)
 └── M10 (Deploy + Polish) ← depends on ALL
```

---

## Phase 1: Backend

### M1: Database + Configuration

> Setup SQLite + SQLAlchemy async, new config settings, startup validation.

**Tasks:**

- [ ] **M1.1** Create `app/db/` package
  - `app/db/__init__.py` — package marker
  - `app/db/database.py` — async engine, session factory
    - `create_async_engine(settings.database_url)`
    - `async_sessionmaker` for dependency injection
    - WAL mode pragma on startup: `PRAGMA journal_mode=WAL`
  - `app/db/models.py` — all 6 ORM models (User, ApiKey, DailyUsage, TokenRevocation, RegistrationAttempt, Blacklist)
  - `app/db/seed.py` — `async def init_db()`: create all tables via `Base.metadata.create_all()`

- [ ] **M1.2** Update `app/config.py`
  - Add 25+ new settings (see TECHNICAL_SPEC_V2.md § Configuration)
  - Add `validate_startup()` method — check SECRET_KEY, ADMIN_KEY not default, at least 1 email provider
  - Keep all existing v1 settings (cache, TTS, etc.)

- [ ] **M1.3** Update `app/main.py` lifespan
  - Call `init_db()` on startup
  - Call `settings.validate_startup()` on startup
  - Create `/data/db/` directory if not exists
  - Start `periodic_cleanup()` background task

- [ ] **M1.4** Update `app/__init__.py`
  - Version `"1.0.0"` → `"2.0.0"`

- [ ] **M1.5** Update `.env.example`
  - All new env vars (database, JWT, email multi-provider, Turnstile, rate limits, proxy, AdSense, admin key)

- [ ] **M1.6** Update `requirements.txt`
  - Add: `sqlalchemy[asyncio]`, `aiosqlite`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `aiosmtplib`, `httpx`

**Deliverable:**
- App starts → SQLite DB created at `./data/db/eidosspeech.db` with all tables
- `settings.validate_startup()` fails loudly if SECRET_KEY is default
- Version shows `"2.0.0"` in health endpoint

---

### M2: Authentication System

> JWT auth, user registration, email verification, password management.
> Contek eidosStack auth pattern (bcrypt, HS256, token types, JTI revocation).

**Tasks:**

- [ ] **M2.1** Create `app/core/jwt_handler.py`
  - `create_token(user_id, email, token_type, expires_delta) -> str`
    - Include: `sub`, `user_id`, `type`, `jti` (uuid4), `iat`, `exp`
  - `decode_token(token, expected_type) -> dict`
    - Validate: signature, expiry, token type match
    - Check JTI not in `token_revocations` table
  - `revoke_token(jti, expires_at)` → insert into `token_revocations`
  - `revoke_all_user_tokens(user_id)` → bulk revoke (for password reset)

- [ ] **M2.2** Create `app/api/v1/auth.py` — 10 endpoints
  - `POST /register` — create user, hash password (bcrypt salt 10), check registration_attempts < 3/IP/day, send verification email
  - `POST /verify-email` — validate token, set is_verified, auto-generate API key (`esk_` + `token_urlsafe(24)`), send welcome email
  - `POST /login` — validate credentials, verify Turnstile (if enabled), return access + refresh tokens
  - `POST /refresh` — validate refresh token, revoke old JTI, issue new pair
  - `POST /logout` — revoke access token JTI
  - `GET /me` — return user profile + API key + today's usage
  - `POST /forgot-password` — generate reset token (1h), send email (critical=true)
  - `POST /reset-password` — validate token, update password, revoke ALL user JTIs
  - `POST /resend-verification` — rate limit 1/5min per email, generate new token
  - `POST /regen-key` — rate limit 1/5min per user, deactivate old key, create new

- [ ] **M2.3** Update `app/models/schemas.py`
  - `RegisterRequest` — email, password (8-128 char), full_name?, tos_accepted (must be true)
  - `LoginRequest` — email, password, turnstile_token?
  - `TokenResponse` — access_token, refresh_token, user?
  - `VerifyEmailRequest` — token
  - `ResetPasswordRequest` — token, new_password (8-128 char)
  - `ForgotPasswordRequest` — email
  - `UserProfile` — email, full_name, is_verified, created_at, api_key, usage
  - `RegenKeyResponse` — api_key

- [ ] **M2.4** Update `app/core/exceptions.py`
  - Add: `AuthenticationError(401)`, `ConflictError(409)`, extend existing

- [ ] **M2.5** Register auth router in `app/api/v1/__init__.py`

- [ ] **M2.6** Turnstile verification (optional)
  - If `EIDOS_TURNSTILE_ENABLED=true`: verify token via `httpx` POST to `https://challenges.cloudflare.com/turnstile/v0/siteverify`
  - If disabled: skip verification

**Deliverable:**
- Register → receive verification email (or log token if SMTP not configured)
- Verify → get API key
- Login → get access + refresh tokens
- Access protected endpoint with `Authorization: Bearer <token>`
- Refresh token on expiry
- Logout → token revoked
- Password reset flow works end-to-end

---

### M3: Email Service

> Multi-provider email with fallback chain. Contek eidosStack EmailDispatcher.

**Tasks:**

- [ ] **M3.1** Create `app/services/email_service.py`
  - `EmailProvider` abstract base — `name`, `send(to, subject, html)`
  - `SmtpProvider` — uses `aiosmtplib`, supports any SMTP (Brevo, Mailtrap, etc.)
  - `ResendProvider` — uses `httpx` REST API
  - `EmailDispatcher` — builds provider chain from config, fallback logic, non-blocking by default
  - Provider chain built from env vars:
    - `EIDOS_SMTP_HOST` set → add SmtpProvider (primary)
    - `EIDOS_SMTP_FALLBACK_HOST` set → add SmtpProvider (fallback)
    - `EIDOS_RESEND_API_KEY` set → add ResendProvider

- [ ] **M3.2** Email templates (inline HTML functions)
  - `verification_email(token, domain)` → subject + HTML (24h expiry, brand header)
  - `reset_password_email(token, domain, ip)` → subject + HTML (1h expiry, IP warning)
  - `welcome_email(api_key, domain)` → subject + HTML (API key, quick start, dashboard link)
  - Dark theme styling matching eidosSpeech brand (emerald accent, dark background)

- [ ] **M3.3** Wire email to auth endpoints
  - `register` → send verification email (non-blocking)
  - `verify-email` → send welcome email (non-blocking)
  - `forgot-password` → send reset email (critical=true)
  - `resend-verification` → send verification email (non-blocking)

**Deliverable:**
- Email sent via primary SMTP
- If primary fails → fallback SMTP → Resend API
- All failures logged but don't block user operations (except password reset)
- Email templates render correctly with brand styling

---

### M4: Rate Limiting + Request Context

> Hybrid rate limiter + resolve_request_context dependency.
> Ref: TECHNICAL_SPEC_V2.md § Rate Limiting System

**Tasks:**

- [ ] **M4.1** Rewrite `app/core/auth.py`
  - Remove old API key validation
  - Implement `resolve_request_context(request, db)` → `RequestContext`
  - Resolution order: X-API-Key → Bearer JWT → Origin check → 403
  - Include `is_own_origin()` helper
  - Check blacklist table on every request

- [ ] **M4.2** Create `app/core/rate_limiter.py`
  - `RateLimiter` class:
    - Per-minute: in-memory `deque` sliding window per identity
    - Per-day: query `daily_usage` table
    - Concurrent: `asyncio.Semaphore(1)` per identity, **reject** if locked
  - `check_and_consume(ctx, db, text_len)` — check all limits, increment on success
  - `get_headers(ctx, usage)` → rate limit response headers dict
  - `acquire_concurrent(ctx)` → async context manager for semaphore
  - `cleanup_stale_entries()` → remove entries older than 5 min from memory

- [ ] **M4.3** Wire to TTS endpoint (`app/api/v1/tts.py`)
  - Inject `RequestContext` via `Depends(resolve_request_context)`
  - Inject `RateLimiter` via `Depends(get_rate_limiter)`
  - Call `rate_limiter.check_and_consume()` before TTS generation
  - Attach `X-RateLimit-*` headers to response
  - Attach `Retry-After` header on 429

- [ ] **M4.4** Update `app/api/v1/batch.py`
  - Return `410 Gone` with message: "Batch TTS is not available in v2. Use v1 at speech.eidosstack.com"

- [ ] **M4.5** Update `app/api/v1/health.py`
  - Add DB connectivity check: `SELECT 1`
  - Add proxy status to response
  - Return `"degraded"` if DB unreachable

- [ ] **M4.6** Add CORS middleware to `app/main.py`
  - `allow_origins`: own domain + localhost (dev)
  - `allow_headers`: Content-Type, Authorization, X-API-Key, X-Admin-Key
  - `expose_headers`: all X-RateLimit-*, X-Cache-*, Retry-After

**Deliverable:**
- Anonymous via Web UI → 5/day, 500 char, 1/min
- Registered via API key → 30/day, 1000 char, 3/min
- External curl without key → 403
- Rate limit exceeded → 429 with Retry-After header
- All responses have `X-RateLimit-*` headers

---

### M5: Proxy Manager + TTS Wiring

> Round-robin proxy + wire proxy to TTS engine.

**Tasks:**

- [ ] **M5.1** Create `app/services/proxy_manager.py`
  - `ProxyManager(proxy_list)` — round-robin cycle
  - `get_next()` → healthy proxy URL or None (direct)
  - `mark_success(proxy)` → reset failure count
  - `mark_failure(proxy)` → increment, disable at 3 failures
  - `reset_all()` → clear failure counts (called by periodic cleanup)
  - Thread-safe with `asyncio.Lock`

- [ ] **M5.2** Update `app/services/tts_engine.py`
  - Accept `ProxyManager` in constructor
  - Pass `proxy=proxy_url` to `edge_tts.Communicate()`
  - On success → `mark_success(proxy)`
  - On failure → `mark_failure(proxy)`, retry with next proxy

- [ ] **M5.3** Wire proxy manager in `app/main.py`
  - Parse `EIDOS_PROXIES` env var → comma-split → `ProxyManager(list)`
  - Empty string → `ProxyManager([])` → always direct
  - Inject via dependency

**Deliverable:**
- `EIDOS_PROXIES=` → TTS works direct (no proxy)
- `EIDOS_PROXIES=http://p1,http://p2` → round-robin, failures tracked
- All proxies fail → fallback to direct
- Proxy status visible in health endpoint

---

## Phase 2: Frontend

### M6: Landing Page

> New landing page — dark theme, hero, demo, API snippet, eidosStack sponsor.
> No AdSense on landing page.

**Tasks:**

- [ ] **M6.1** Create `app/static/landing.html`
  - Tailwind CSS CDN + Lucide Icons + Inter font
  - Tailwind config inline (brand color `#10B981`, Inter font)
  - Dark theme: `bg-gray-950` body, `bg-gray-900` cards
  - Sections:
    1. **Navbar** — logo, "Try Now" button, "Get API Key" button
    2. **Hero** — "Free Text-to-Speech API", "1,200+ AI Voices · 75+ Languages", CTA
    3. **Stats** — 3 cards: 1,200+ Voices, 75+ Languages, Free API
    4. **Live Demo** — embedded mini player with pre-generated audio sample
    5. **API Snippet** — curl example with copy button
    6. **eidosStack Sponsor** — "Part of eidosStack ecosystem" banner
    7. **Footer** — "Powered by eidosStack" + ToS link

- [ ] **M6.2** Add page route in `app/main.py`
  - `GET /` → serve `landing.html`
  - `GET /app` → serve `index.html` (TTS app)

**Deliverable:**
- `eidosspeech.xyz/` → landing page loads, dark theme, responsive
- "Try Now" → navigates to `/app`
- "Get API Key" → navigates to `/app#register`
- No AdSense on landing page
- eidosStack sponsor banner visible

---

### M7: TTS App Rewrite

> Rewrite index.html with Tailwind dark theme, auth modals, info banner, AdSense.

**Tasks:**

- [ ] **M7.1** Create `app/static/js/toast.js`
  - `showToast(message, type, duration)` — type: success/error/info/warning
  - Position: top-right fixed, max 3 visible
  - Animation: slide-in from right, fade-out
  - Colors: emerald (success), red (error), blue (info), amber (warning)
  - Auto-dismiss after `duration` (default 5000ms)

- [ ] **M7.2** Create `app/static/js/auth.js`
  - `AuthStore` object — state manager
  - States: `UNAUTHENTICATED`, `AUTHENTICATED`, `SESSION_EXPIRED`
  - Methods: `init()`, `setAuth()`, `clearAuth()`, `getToken()`, `isAuthenticated()`
  - Persist to `localStorage` key `eidosspeech_auth`
  - `_evaluateSession()` — check expiry, auto-refresh, called every 60s

- [ ] **M7.3** Update `app/static/js/api-client.js`
  - Wrap all requests through `ApiClient.request(method, path, body)`
  - Auto-attach `Authorization: Bearer <token>` if authenticated
  - Auto-refresh on 401 (contek eidosStack): retry original request after refresh
  - If refresh fails → `AuthStore.clearAuth()` + toast "Session expired"

- [ ] **M7.4** Rewrite `app/static/index.html`
  - Full Tailwind dark theme rewrite
  - **Navbar**: logo, Login/Register buttons (or user menu if logged in)
  - **Info Banner**: 3 states (anonymous, registered, limit-reached modal)
    - Anonymous: show remaining requests + register CTA
    - Registered: show usage + API key preview + dashboard link
    - Limit reached: modal with register benefits
  - **AdSense slots**: top banner (728x90), below player (300x250)
  - **TTS controls**: preserved from v1 (text input, voice selection, sliders, generate)
  - **Auth modals**:
    - Register: email, password, full_name, ToS checkbox, submit
    - Login: email, password, Turnstile widget (if enabled), submit
    - Forgot password: email, submit
  - **eidosStack banner**: below player
  - **Footer**: "Powered by eidosStack" + links

- [ ] **M7.5** Update `app/static/js/app.js`
  - Integrate `AuthStore` — update navbar, info banner on auth state change
  - Character counter respects tier limit (500 or 1000)
  - Fetch usage on page load (if authenticated)
  - Update info banner after each TTS generation
  - Hash-based modal: `#register` → auto-open register modal, `#login` → login modal
  - AdSense: load script if `adsense_client_id` provided, show placeholder if not

- [ ] **M7.6** Update `app/static/css/style.css`
  - Minimal custom CSS (Tailwind handles 95%)
  - Custom range slider styling
  - Modal animation keyframes (if not using Tailwind animate)
  - AdSense container sizing

**Deliverable:**
- `/app` → dark themed TTS tool loads
- Anonymous: can generate 5x/day, sees info banner with register CTA
- Login/Register modals work, auth state persists across page refresh
- After login: info banner shows usage + API key
- Limit reached → modal with register benefits
- AdSense slots render (or placeholder in dev)
- Toast notifications for all actions

---

### M8: User Dashboard + Static Pages

> Dashboard, ToS, verify-email, reset-password, api-docs pages.

**Tasks:**

- [ ] **M8.1** Create `app/static/dashboard.html`
  - Auth guard: redirect to `/app#login` if not authenticated
  - **Today's Usage**: progress bar (requests used/limit), chars used
  - **API Key**: display full key, copy button, regenerate button (with confirmation)
  - **Limits**: tier info card (Free tier, char limit, req/day, req/min, API access)
  - **Quick Start**: curl, Python, JavaScript code snippets with copy buttons
  - Dark theme, card-based layout

- [ ] **M8.2** Create `app/static/tos.html`
  - Terms of Service page
  - Sections: service description, usage limits, acceptable use, email marketing consent, data handling, liability
  - Include `tos_accepted_at` timestamp requirement
  - Dark theme, readable typography

- [ ] **M8.3** Create `app/static/verify-email.html`
  - Extract `token` from URL query params
  - Auto-submit to `POST /api/v1/auth/verify-email`
  - Success: show API key + "Go to App" button, auto-login
  - Failure: show error + "Resend Verification" button

- [ ] **M8.4** Create `app/static/reset-password.html`
  - Extract `token` from URL query params
  - Form: new password, confirm password
  - Submit to `POST /api/v1/auth/reset-password`
  - Success: "Password updated" + "Login" button
  - Failure: "Invalid or expired link" + "Request new link" button

- [ ] **M8.5** Create `app/static/api-docs.html`
  - Custom API documentation page
  - Sections:
    - Authentication (API key header, JWT bearer)
    - TTS endpoint (request/response, examples in curl/Python/JS)
    - Voices endpoint (query params, response format)
    - Rate limits (table, headers explanation)
    - Error codes (table with all HTTP codes + error types)
  - Interactive "Try it" with API key input field
  - Dark theme, code blocks with syntax highlighting

- [ ] **M8.6** Add page routes in `app/main.py`
  - `GET /dashboard` → serve `dashboard.html`
  - `GET /tos` → serve `tos.html`
  - `GET /verify-email` → serve `verify-email.html`
  - `GET /reset-password` → serve `reset-password.html`
  - `GET /api-docs` → serve `api-docs.html`

**Deliverable:**
- Dashboard: usage stats, API key management, quick start guide
- Email verification: click link → verify → see API key → go to app
- Password reset: click link → new password → login
- ToS page: complete terms with marketing consent
- API docs: interactive, comprehensive, dark theme

---

## Phase 3: Admin + Deploy

### M9: Admin Panel

> Admin API endpoints + admin dashboard UI.

**Tasks:**

- [ ] **M9.1** Create `app/api/v1/admin.py`
  - Admin auth dependency: check `X-Admin-Key` header
  - 7 endpoints (see MASTERPLAN_V2.md § Phase 3):
    - `GET /stats` — aggregate stats
    - `GET /users` — paginated user list with search/sort
    - `GET /usage` — daily aggregates (last N days)
    - `GET /usage/voices` — popular voices/languages
    - `POST /keys/{id}/disable` — disable key + revoke JTIs
    - `POST /users/{id}/ban` — ban user + disable key + revoke JTIs
    - `POST /blacklist` — add IP or email to blacklist

- [ ] **M9.2** Register admin router in `app/api/v1/__init__.py`
  - Prefix: `/api/v1/admin`
  - All endpoints require `X-Admin-Key` header

- [ ] **M9.3** Create `app/static/admin.html`
  - Admin key input on load (stored in sessionStorage, NOT localStorage)
  - Dark theme, sidebar navigation (contek eidosStack style):
    - **Stats**: total users, verified, active keys, requests today/yesterday, cache stats
    - **Users**: table (email, verified, active, API key, usage today, ban button)
    - **Usage**: daily chart (last 30 days) — simple bar chart via canvas/SVG
    - **Blacklist**: add/remove IP or email, list current entries
  - Card-based layout, emerald accent
  - All data fetched via `X-Admin-Key` header

**Deliverable:**
- `/admin` → admin dashboard loads (after entering admin key)
- Stats, users, usage, blacklist sections all functional
- Ban user → user can't login/use API
- Blacklist IP → all requests from IP blocked

---

### M10: Deploy + Polish

> Docker updates, nginx, final testing, cleanup.

**Tasks:**

- [ ] **M10.1** Update `Dockerfile`
  - Add `/data/db/` directory creation
  - Ensure `/data/cache/` directory exists (from v1)

- [ ] **M10.2** Update `docker-compose.nginx.yml`
  - Add `app_data` volume mapping for `/data/db`
  - Or use single volume for entire `/data/` directory

- [ ] **M10.3** Create `nginx-public.conf`
  - SSL config for `eidosspeech.xyz`
  - Proxy pass to FastAPI
  - Static asset caching (7 day)
  - Auth endpoint rate limiting (nginx layer)
  - HTTP → HTTPS redirect
  - Client max body size: 1MB

- [ ] **M10.4** Periodic cleanup verification
  - Expired token revocations cleaned (> 7 days)
  - Old registration attempts cleaned (> 7 days)
  - Unverified users cleaned (> 72 hours)
  - Stale rate limit memory entries cleaned
  - Proxy failure counters reset

- [ ] **M10.5** Error handling audit
  - All auth errors return consistent JSON format
  - Rate limit errors include Retry-After header
  - TTS errors don't expose internal details
  - DB errors caught and wrapped
  - Proxy errors logged, fallback to direct

- [ ] **M10.6** Logging verification
  - All security events logged (register, login, auth fail, rate limit, admin action)
  - Log format: structured with timestamp, level, event type
  - Sensitive data NOT logged (passwords, full tokens)

- [ ] **M10.7** End-to-end testing
  - Anonymous flow: landing → /app → generate (5x) → limit modal → register
  - Register flow: register → verify email → get API key → login
  - API flow: curl with API key → generate → rate limit headers correct
  - Dashboard: usage stats accurate, API key management works
  - Admin: stats accurate, ban user → blocked, blacklist → blocked
  - Proxy: test with/without proxies
  - Email: test fallback chain (disable primary → fallback triggers)
  - Token refresh: wait 15min → auto-refresh → seamless
  - Password reset: forgot → email → reset → login with new password

- [ ] **M10.8** Update FastAPI docs
  - All endpoints have description + examples
  - OpenAPI schema complete at `/docs`
  - Swagger UI accessible

**Deliverable:**
- `docker compose up` → eidosSpeech v2 running at `eidosspeech.xyz`
- All 25 verification checklist items pass (see MASTERPLAN_V2.md)
- SQLite persistent via Docker volume
- Nginx with SSL + static caching + auth rate limiting
- Clean logs, no errors in normal operation

---

## File Creation/Modification Summary per Milestone

| Milestone | New Files | Modified Files |
|-----------|-----------|----------------|
| **M1** | `app/db/__init__.py`, `database.py`, `models.py`, `seed.py` | `config.py`, `main.py`, `__init__.py`, `requirements.txt`, `.env.example` |
| **M2** | `app/core/jwt_handler.py`, `app/api/v1/auth.py` | `exceptions.py`, `schemas.py`, `api/v1/__init__.py` |
| **M3** | `app/services/email_service.py` | `app/api/v1/auth.py` (wire email) |
| **M4** | `app/core/rate_limiter.py` | `app/core/auth.py` (rewrite), `tts.py`, `batch.py`, `health.py`, `main.py` |
| **M5** | `app/services/proxy_manager.py` | `tts_engine.py`, `main.py` |
| **M6** | `app/static/landing.html` | `main.py` (page routes) |
| **M7** | `app/static/js/auth.js`, `toast.js` | `index.html` (rewrite), `app.js`, `api-client.js`, `style.css` |
| **M8** | `dashboard.html`, `tos.html`, `verify-email.html`, `reset-password.html`, `api-docs.html` | `main.py` (page routes) |
| **M9** | `app/api/v1/admin.py`, `app/static/admin.html` | `api/v1/__init__.py` |
| **M10** | `nginx-public.conf` | `Dockerfile`, `docker-compose.nginx.yml` |

---

## Development Order (Linear)

```
Week 1: M1 → M2 → M3
  M1: DB + config (foundation)
  M2: Auth system (depends M1)
  M3: Email service (depends M1, wires into M2)

Week 2: M4 → M5
  M4: Rate limiting + request context (depends M1, M2)
  M5: Proxy + TTS wiring (depends M1, M4)

Week 3: M6 → M7
  M6: Landing page (independent frontend)
  M7: TTS app rewrite (depends M4, M5 for backend)

Week 4: M8 → M9 → M10
  M8: Dashboard + static pages (depends M2, M7)
  M9: Admin panel (depends M4, M8)
  M10: Deploy + polish (depends all)
```

**Total: ~4 weeks estimated.**
Backend heavy (M1-M5) first, then frontend (M6-M8), then admin + deploy (M9-M10).

---

## Testing Checklist per Milestone

### M1 Tests
- [ ] App starts without error
- [ ] SQLite file created at `./data/db/eidosspeech.db`
- [ ] All 6 tables exist
- [ ] WAL mode active: `PRAGMA journal_mode` returns `wal`
- [ ] Startup fails if SECRET_KEY is default

### M2 Tests
- [ ] Register with valid data → 201
- [ ] Register with existing email → 409
- [ ] Register with weak password → 400
- [ ] Verify email with valid token → 200 + API key
- [ ] Verify with expired token → 400
- [ ] Login with correct credentials → 200 + tokens
- [ ] Login with wrong password → 401
- [ ] Access /me with valid token → 200
- [ ] Access /me with expired token → 401
- [ ] Refresh token → new token pair
- [ ] Logout → token revoked, /me returns 401
- [ ] Reset password → new password works, old doesn't

### M3 Tests
- [ ] Verification email sent via primary SMTP
- [ ] Primary SMTP down → fallback SMTP used
- [ ] All SMTP down → Resend API used
- [ ] All providers down → registration still succeeds (non-blocking)
- [ ] Password reset → email sent (critical, throws if all fail)

### M4 Tests
- [ ] Anonymous via Web UI (Origin match) → 5/day, 500 char
- [ ] Registered via API key → 30/day, 1000 char
- [ ] External curl without key → 403
- [ ] 6th anonymous request → 429
- [ ] 2 concurrent requests → second gets 429
- [ ] Response has `X-RateLimit-*` headers
- [ ] 429 response has `Retry-After` header
- [ ] Blacklisted IP → 403

### M5 Tests
- [ ] No proxy configured → direct works
- [ ] Proxy configured → round-robin used
- [ ] Proxy fails 3x → skipped, next proxy used
- [ ] All proxies fail → fallback to direct
- [ ] Health endpoint shows proxy status

### M6 Tests
- [ ] Landing page loads at `/`
- [ ] Dark theme renders correctly
- [ ] "Try Now" → navigates to `/app`
- [ ] Responsive on mobile/tablet

### M7 Tests
- [ ] TTS app loads at `/app`
- [ ] Generate works without login (anonymous)
- [ ] Info banner shows remaining requests
- [ ] Register modal opens on "Register" click or `#register` hash
- [ ] Login → info banner updates with usage + API key
- [ ] Limit reached → modal appears
- [ ] Toast notifications visible for all actions
- [ ] Auth persists across page refresh

### M8 Tests
- [ ] Dashboard loads (authenticated only)
- [ ] Usage stats accurate
- [ ] API key copy works
- [ ] Regenerate key works (with cooldown)
- [ ] Verify-email page: valid token → success
- [ ] Reset-password page: form + submit works
- [ ] ToS page renders completely
- [ ] API docs page loads with all sections

### M9 Tests
- [ ] Admin panel requires `X-Admin-Key`
- [ ] Stats endpoint returns accurate data
- [ ] Users list paginated, searchable
- [ ] Ban user → user blocked
- [ ] Blacklist IP → requests from IP blocked
- [ ] Disable API key → key stops working

### M10 Tests
- [ ] `docker compose up` → app running
- [ ] SQLite persistent across container restart
- [ ] All 25 verification checklist items pass
- [ ] nginx SSL working
- [ ] No errors in logs during normal operation
