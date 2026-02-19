# eidosSpeech v2 — Public Release Roadmap

> v2 = public release, completely separate dari v1 (internal).
> v1 docs: [../docs/MASTERPLAN.md](../docs/MASTERPLAN.md) | [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
> v2 masterplan: [MASTERPLAN_V2.md](./MASTERPLAN_V2.md)

---

## Overview

eidosSpeech v2 adalah versi **public** — beda codebase, beda domain, beda database dari v1. Model bisnis: **free + ads** (Google AdSense di TTS App page). Tidak ada paid tier.

v2 **fully independent** — punya auth, database, admin sendiri. Hubungan dengan eidosStack hanya cross-promotion/sponsor.

**Voices**: 1,200+ (Speechma-style counting). Same engine as v1 (`edge-tts`).

---

## Tier System (2 Tier)

| Feature | Anonymous (No Register) | Registered (Free) |
|---------|:-----------------------:|:------------------:|
| **Web UI** | Yes (+ads) | Yes (+ads) |
| **API access** | **No** (Web UI only) | **Yes** |
| **Karakter/request** | 500 | 1.000 |
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

> Internal use (eidosOne, eidosLumina) tetap pakai v1 di `speech.eidosstack.com`. v2 murni public.

---

## Architecture

### Tier Detection — `resolve_request_context`

```
Request masuk
  ├── Ada X-API-Key header?
  │   ├── Key valid (registered) → "registered" tier
  │   └── Key invalid → 403 Forbidden
  ├── Ada Authorization: Bearer <jwt>?
  │   └── Decode → load user's API key → "registered" tier
  └── Tidak ada key / token
      ├── Origin = domain sendiri? → "anonymous" (Web UI, IP limit)
      └── Origin = external → 403 "Register for API access"
```

### Rate Limiting (In-memory + SQLite, No Redis)

```python
# Anonymous (Web UI only): per IP
char_limit = 500
rate_limit = "1/minute"
daily_limit = "5/day"

# Registered: per API key + per IP
char_limit = 1000
rate_limit = "3/minute"
daily_limit = "30/day"
```

- Per-minute: in-memory sliding window
- Per-day: `daily_usage` table in SQLite
- IP rate limit always on (even with API key)
- Concurrent: 1 per identity — **reject** (not queue) if already processing
- Daily reset: **UTC midnight**
- Response headers: `X-RateLimit-Tier`, `X-RateLimit-Remaining-Day`, `Retry-After` (on 429)

### Auth (contek eidosStack pattern)

- Password: bcrypt salt 10, min 8 char, max 128 char
- JWT: HS256, access 15 min, refresh 7 day
- Token types: `access`, `refresh`, `verify`, `reset`
- Token revocation via JTI
- Turnstile CAPTCHA on login (optional, configurable)
- Tokens: JSON body (frontend stores in localStorage)
- Auto-refresh: 401 → try refresh token → retry original request (contek eidosStack pattern)
- API key: `esk_` + `secrets.token_urlsafe(24)` = 36 char, 192-bit entropy

### Database — SQLite

Tables: `users`, `api_keys`, `daily_usage`, `token_revocations`, `registration_attempts`

### Proxy — Optional, Built-in

```env
EIDOS_PROXIES=                                          # kosong = direct, no proxy
EIDOS_PROXIES=http://proxy1,http://proxy2,...            # diisi = round-robin
```

Webshare free proxy (10-20) sudah cukup. Round-robin + failure tracking + fallback to direct.

### Frontend Stack

| Stack | Alasan |
|-------|--------|
| Tailwind CSS (CDN) | Modern, no build step |
| Lucide Icons (CDN) | Clean icons |
| Inter (Google Fonts) | Clean sans-serif |
| Vanilla JS | No framework, no bundler |

**Design**: Dark theme (contek eidosStack style) — `bg-gray-950` body, emerald/green accent, `rounded-2xl` cards, `border-white/10` borders.

### Email Service (Multi-Provider Fallback)

Contek eidosStack EmailDispatcher pattern — fallback chain, non-blocking:

```
Primary SMTP → Fallback SMTP → Resend API → log error (user can resend)
```

- Email send = best-effort, **non-blocking** — registration proceeds even if email fails
- Min 1 provider harus configured (startup validation)
- Templates: verification (24h expiry), password reset (1h expiry), welcome (API key)

### CORS & Error Handling

- CORS restricted to own domain + localhost (dev)
- Consistent error format: `{"error": "ErrorType", "message": "...", "detail": {...}}`
- 429 response includes `Retry-After` header
- Daily rate limit reset: **UTC midnight**

### Ads (TTS App page only)

```
TTS App (/app):
  [Info Banner: limits + register benefit]
  [AdSense Banner 728x90]
  [Text Input] [Voice Selection]
  [Audio Player]
  [AdSense Rectangle 300x250]
  [eidosStack Ecosystem Banner]

Landing page (/):
  NO AdSense — clean, professional
  eidosStack Ecosystem Sponsor Banner
```

---

## Endpoint Access Matrix

| Endpoint | Anonymous (Web UI) | Registered |
|----------|:------------------:|:----------:|
| `GET /` | Landing page | Landing page |
| `GET /app` | TTS (5/day, 500ch) | TTS (30/day, 1Kch) |
| `POST /api/v1/tts` | **Web UI only** | Yes |
| `GET /api/v1/voices` | Yes | Yes |
| `GET /api/v1/health` | Yes | Yes |
| `POST /api/v1/auth/*` | Yes | Yes |
| `GET /dashboard` | No | Yes |
| `GET /docs` | Yes (Swagger) | Yes |
| `GET /api-docs` | Yes | Yes |
| `GET /api/v1/admin/*` | No | `X-Admin-Key` header |

---

## User Flows

### Anonymous → Try TTS
```
eidosspeech.xyz → Landing page → "Try Now" → /app
  → Generate TTS (5x/hari, 500 char, Web UI only)
  → Info banner: "Register for 30 req/day, 1000 chars, API access"
  → Limit habis → Modal: register benefit + CTA
```

### Register → Get API Key
```
/app → "Register" → Modal (email + password + agree ToS)
  → Email verification link sent (expire 24h)
  → Click verify → API key auto-generated (esk_<random>)
  → Redirect /app (logged in, 30/day, 1000 char, API access)
```

### API Usage (Registered)
```
curl -X POST https://eidosspeech.xyz/api/v1/tts \
  -H "X-API-Key: esk_a1b2c3d4e5f6g7h8" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "id-ID-GadisNeural"}'
```

---

## Config (.env)

```env
# Database
EIDOS_DATABASE_URL=sqlite+aiosqlite:///./data/eidosspeech.db

# JWT / Auth
EIDOS_SECRET_KEY=change-me-in-production-min-64-bytes
EIDOS_JWT_ALGORITHM=HS256
EIDOS_ACCESS_TOKEN_EXPIRE_MINUTES=15
EIDOS_REFRESH_TOKEN_EXPIRE_DAYS=7

# Email — Primary SMTP (multi-provider fallback, contek eidosStack)
EIDOS_SMTP_HOST=smtp-relay.brevo.com
EIDOS_SMTP_PORT=587
EIDOS_SMTP_USERNAME=
EIDOS_SMTP_PASSWORD=
EIDOS_SMTP_FROM=eidosSpeech <noreply@eidosspeech.xyz>

# Email — Fallback SMTP (optional)
EIDOS_SMTP_FALLBACK_HOST=
EIDOS_SMTP_FALLBACK_PORT=587
EIDOS_SMTP_FALLBACK_USERNAME=
EIDOS_SMTP_FALLBACK_PASSWORD=

# Email — Resend API fallback (optional)
EIDOS_RESEND_API_KEY=

# Cloudflare Turnstile (optional)
EIDOS_TURNSTILE_SITE_KEY=
EIDOS_TURNSTILE_SECRET_KEY=
EIDOS_TURNSTILE_ENABLED=false

# Rate Limits — Anonymous
EIDOS_ANON_CHAR_LIMIT=500
EIDOS_ANON_REQ_PER_DAY=5
EIDOS_ANON_REQ_PER_MIN=1

# Rate Limits — Registered
EIDOS_FREE_CHAR_LIMIT=1000
EIDOS_FREE_REQ_PER_DAY=30
EIDOS_FREE_REQ_PER_MIN=3

# Proxy (optional)
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

Startup validation: `SECRET_KEY` must not be default + at least 1 email provider configured.

---

## Implementation Priority

### Phase 1: Backend (DB + Auth + Rate Limit + Email + Proxy)
1. SQLite + SQLAlchemy async + WAL mode
2. Multi-provider email service (Primary SMTP → Fallback SMTP → Resend API)
3. User registration + email verify + auto API key
4. JWT auth (access 15m + refresh 7d + auto-refresh)
5. `resolve_request_context` (anonymous vs registered)
6. Rate limiting (in-memory + SQLite) + concurrent reject
7. Origin check (anonymous = Web UI only)
8. Proxy manager (optional, built-in)
9. CORS policy + error response format + startup validation
10. Periodic cleanup tasks (expired tokens, unverified users)

### Phase 2: Frontend (Landing + App + Dashboard)
1. Landing page (Tailwind dark theme, hero, demo, API snippet, eidosStack sponsor)
2. TTS App rewrite (Tailwind dark, auth modal, info banner, AdSense, toast notifications)
3. Auth state manager (localStorage, auto-refresh on 401)
4. User dashboard (usage, API key, regen, limits, quick start)
5. ToS, verify-email, reset-password, api-docs pages

### Phase 3: Admin + Deploy
1. Admin panel with `X-Admin-Key` auth (stats, users, usage, ban, blacklist)
2. Admin dashboard UI (dark theme, sidebar, contek eidosStack style)
3. nginx config untuk public domain
4. Docker volume untuk SQLite
5. Version bump → 2.0.0

---

## Abuse Protection

| Protection | How |
|------------|-----|
| 1 API key per email | Registration enforce |
| Max 3 register per IP per day | `registration_attempts` table |
| Same email blocked regardless of IP | UNIQUE constraint |
| IP rate limit always on | Even with API key |
| Concurrent = 1 per identity | Reject, not queue |
| Turnstile CAPTCHA | Login form (optional) |
| Email verification | Required for API key |
| Blacklist IP/email | Admin endpoint (permanent) |
| Token revocation | JTI-based |
| Password min 8, max 128 char | Register + reset validation |
| Unverified user cleanup | Auto-delete after 72h |

---

## Voices

**1,200+ voices** (Speechma-style counting)

- ~310 native voices (language-specific)
- 12 multilingual voices (work with all languages)
- native + (multilingual × supported languages) = 1,200+
- Engine: `edge-tts` (Microsoft Azure Neural TTS)

12 multilingual voices: Andrew, Ava, Brian, Emma, William, Remy, Vivienne, Florian, Seraphina, Giuseppe, Hyunsu, Thalita

---

## Cost

### Launch: $0/bulan
edge-tts ($0) + Webshare free proxy ($0) + VPS existing ($0) + Brevo free SMTP 300/day ($0) + Resend free 100/day ($0) + Turnstile ($0)

### Scale Up
Webshare paid: $4/mo · Domain: ~$1/mo · SMTP upgrade: ~$20/mo · AdSense: +$??

---

## Reference

- v2 Masterplan: [MASTERPLAN_V2.md](./MASTERPLAN_V2.md)
- v1 docs: [../docs/MASTERPLAN.md](../docs/MASTERPLAN.md) | [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- Auth reference: eidosStack (`D:\Project\eidosstack\eidosstack-license-server\src\routes\user\auth.routes.js`)
