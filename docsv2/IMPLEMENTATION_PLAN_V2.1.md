# eidosSpeech v2.1 — Implementation Plan: Advanced Features

> **Base**: Production v2.0.0 at `D:\Project\eidossSpeechV2`
> **Domain**: eidosspeech.xyz
> **Goal**: Tambah fitur-fitur canggih tanpa breaking existing functionality
> **Approach**: Incremental — setiap feature bisa di-deploy independen

---

## Production State Audit (Februari 2026)

### What's Running Now

```
Version:      2.0.0
Framework:    FastAPI 0.115.6 + SQLAlchemy 2.0.36 + SQLite (WAL mode)
Auth:         JWT (access 15min + refresh 7day) + API Key (esk_*)
TTS Engine:   edge-tts ≥7.0.0 → MP3 audio
Rate Limit:   3-tier hybrid (in-memory per-min + SQLite per-day + concurrent semaphore)
              Anonymous: 5/day, 1/min, 500 char
              Registered API: 30/day, 3/min, 1000 char
              Registered WebUI: 30/day, 3/min, 2000 char
Cache:        File-based LRU (5GB, 30-day TTL, SHA256 keys)
Proxy:        Round-robin ProxyManager with auto-recovery + direct fallback
Email:        Multi-provider (Brevo → Mailtrap → Resend) with circuit breaker
Bot Protect:  Cloudflare Turnstile (optional)
Frontend:     Tailwind CSS CDN + Vanilla JS, dark theme (#050a06), Inter + JetBrains Mono
DB Tables:    9 (users, api_keys, daily_usage, token_revocations,
              registration_attempts, blacklist, login_attempts, audit_logs, page_views)
Pages:        11 (landing, app, dashboard, admin, api-docs, blog, tos, privacy,
              verify-email, reset-password, robots/sitemap)
```

### Live Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/tts` | API Key / JWT | Generate TTS audio (rate-limited) |
| GET | `/api/v1/voices` | None | List 1,200+ voices |
| GET | `/api/v1/health` | None | System health (DB, cache, proxy, uptime) |
| POST | `/api/v1/batch` | — | 410 Gone (deprecated from v1) |
| GET | `/api/v1/auth/turnstile-config` | None | Turnstile config |
| POST | `/api/v1/auth/register` | Turnstile | Create account |
| POST | `/api/v1/auth/verify-email` | None | Verify → auto-generate API key |
| POST | `/api/v1/auth/login` | Turnstile | Login → JWT pair |
| POST | `/api/v1/auth/refresh` | Refresh JWT | New token pair |
| POST | `/api/v1/auth/logout` | Access JWT | Revoke token |
| GET | `/api/v1/auth/me` | Access JWT | Profile + usage |
| POST | `/api/v1/auth/forgot-password` | None | Send reset email |
| POST | `/api/v1/auth/reset-password` | None | Reset password |
| POST | `/api/v1/auth/resend-verification` | Turnstile | Resend verify |
| POST | `/api/v1/auth/regen-key` | Access JWT | Regenerate API key (5min cooldown) |
| GET/POST | `/api/v1/admin/*` | X-Admin-Key | 11 admin endpoints |

### Current Frontend Architecture

```
app/static/
├── landing.html, index.html (TTS app), dashboard.html, admin.html
├── api-docs.html, blog.html, tos.html, privacy.html
├── verify-email.html, reset-password.html
├── robots.txt, sitemap.xml
└── js/
    ├── api-client.js    # HTTP client with auto-refresh on 401
    ├── auth.js          # AuthStore (localStorage: user, tokens, API key)
    └── toast.js         # Toast notifications (success, error, info)
```

### Current TTS Engine Pattern

```python
# app/services/tts_engine.py — v2 pattern (proxy-aware)
class TTSEngine:
    def __init__(self, proxy_manager: ProxyManager): ...

    async def synthesize(self, text, voice, rate, pitch, volume) -> bytes:
        for attempt in range(1, max_retries + 1):
            proxy_url = await self.proxy_manager.get_next()
            if attempt == max_retries:
                proxy_url = None  # force direct on final try
            try:
                audio = await self._generate(text, voice, rate, pitch, volume, proxy_url)
                if proxy_url: await self.proxy_manager.mark_success(proxy_url)
                return audio
            except Exception:
                if proxy_url: await self.proxy_manager.mark_failure(proxy_url)
                await asyncio.sleep(retry_delay * attempt)

    async def _generate(self, text, voice, rate, pitch, volume, proxy) -> bytes:
        kwargs = {"text": text, "voice": voice, "rate": rate, "pitch": pitch, "volume": volume}
        if proxy: kwargs["proxy"] = proxy
        communicate = edge_tts.Communicate(**kwargs)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        return b"".join(audio_chunks)
```

### Current TTS Endpoint Pattern

```python
# app/api/v1/tts.py — v2 pattern (rate-limited, context-aware)
@router.post("/tts")
async def generate_tts(
    tts_request: TTSRequest,
    request: Request,
    ctx: RequestContext = Depends(resolve_request_context),  # anon/registered
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    usage = await rate_limiter.check_and_consume(ctx, db, len(text))  # char + daily + min
    cache_key = compute_cache_key(tts_request)                        # SHA256
    cached_path = cache.get(cache_key)                                # file check
    if cached_path: return FileResponse(cached_path, headers=rl_headers)
    async with rate_limiter.acquire_concurrent(ctx):                  # semaphore
        audio_bytes = await tts_engine.synthesize(...)
        cached_path = cache.put(cache_key, audio_bytes)
    return FileResponse(cached_path, headers=rl_headers)
```

### Current Dependencies

```
fastapi==0.115.6          uvicorn[standard]==0.32.1
sqlalchemy==2.0.36        aiosqlite==0.20.0
python-jose[cryptography]==3.3.0   passlib[bcrypt]==1.7.4
bcrypt==4.1.3             edge-tts>=7.0.0
aiosmtplib==3.0.2         httpx==0.28.1
pydantic==2.10.3          pydantic-settings==2.6.1
python-multipart==0.0.20
```

### Current TTSRequest Schema

```python
class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice: str = Field(default="id-ID-GadisNeural")
    rate: str = Field(default="+0%")
    pitch: str = Field(default="+0Hz")
    volume: str = Field(default="+0%")
```

### Current Cache Key Computation

```python
def compute_cache_key(req: TTSRequest) -> str:
    content = json.dumps({
        "text": req.text, "voice": req.voice,
        "rate": req.rate, "pitch": req.pitch,
        # volume excluded — edge-tts ignores it
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(content).hexdigest()
```

---

## New Features Overview

| # | Feature | Backend | Frontend | New Deps | Priority |
|---|---------|---------|----------|----------|----------|
| F1 | SRT/Subtitle Generator | New endpoint + SubMaker | Download SRT button | None | P1 |
| F2 | Voice Emotion/Style Control | SSML wrapper in tts_engine | Style dropdown + slider | None | P1 |
| F3 | Voice Character Presets | JSON config + endpoint | Preset cards grid | None | P1 |
| F4 | Audio Waveform Visualizer | None | Canvas + Web Audio API | None | P2 |
| F5 | Multi-Voice Script Mode | New endpoint + audio merge | Script editor + voice map | pydub | P2 |
| F6 | Voice Comparison Tool | None (parallel /tts calls) | Multi-player UI | None | P2 |
| F7 | Pronunciation Editor | SSML `<sub>` preprocessing | Word click UI | None | P3 |
| F8 | Embeddable Widget | New /embed endpoint | iframe mini player | None | P3 |
| F9 | Voice Favorites | None | localStorage + star | None | P3 |
| F10 | Keyboard Shortcuts | None | Event listeners | None | P3 |

---

## F1: SRT/Subtitle Generator

### Why
Edge-tts punya `SubMaker` built-in — word-level timing data gratis. Content creator YouTube/TikTok butuh ini. Zero additional dependency.

### Edge-TTS SubMaker API

```python
communicate = edge_tts.Communicate(text="Hello world", voice="en-US-GuyNeural")
submaker = edge_tts.SubMaker()

async for chunk in communicate.stream():
    if chunk["type"] == "audio":
        audio_chunks.append(chunk["data"])
    elif chunk["type"] == "WordBoundary":
        submaker.create_sub(chunk["offset"], chunk["duration"], chunk["text"])

srt_content = submaker.generate_subs(words_per_cue=10)
```

### Backend Changes

**File: `app/services/tts_engine.py`** — tambah method di TTSEngine:

```python
async def synthesize_with_subtitles(
    self, text, voice, rate, pitch, volume, words_per_cue=10,
) -> tuple[bytes, str]:
    """Generate audio + SRT. Returns (mp3_bytes, srt_string)."""
    last_error = None
    for attempt in range(1, settings.tts_max_retries + 1):
        proxy_url = await self.proxy_manager.get_next()
        if attempt == settings.tts_max_retries:
            proxy_url = None  # force direct on last try

        try:
            audio, srt = await self._generate_with_subs(
                text, voice, rate, pitch, volume, proxy_url, words_per_cue
            )
            if proxy_url:
                await self.proxy_manager.mark_success(proxy_url)
            return audio, srt
        except Exception as e:
            last_error = e
            if proxy_url:
                await self.proxy_manager.mark_failure(proxy_url)
            if attempt < settings.tts_max_retries:
                await asyncio.sleep(settings.tts_retry_delay * attempt)

    raise RuntimeError(f"TTS+SRT failed after retries: {last_error}")

async def _generate_with_subs(
    self, text, voice, rate, pitch, volume, proxy, words_per_cue
) -> tuple[bytes, str]:
    kwargs = {"text": text, "voice": voice, "rate": rate, "pitch": pitch, "volume": volume}
    if proxy:
        kwargs["proxy"] = proxy

    communicate = edge_tts.Communicate(**kwargs)
    submaker = edge_tts.SubMaker()
    audio_chunks = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            submaker.create_sub(chunk["offset"], chunk["duration"], chunk["text"])

    if not audio_chunks:
        raise RuntimeError("No audio data received")

    return b"".join(audio_chunks), submaker.generate_subs(words_per_cue)
```

**File: `app/api/v1/tts.py`** — tambah endpoint:

```python
from fastapi.responses import JSONResponse

@router.post("/tts/subtitle")
async def generate_tts_with_subtitle(
    tts_request: TTSSubtitleRequest,
    request: Request,
    ctx: RequestContext = Depends(resolve_request_context),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Generate TTS audio + SRT subtitle."""
    text = tts_request.text.strip()
    usage = await rate_limiter.check_and_consume(ctx, db, len(text))
    cache = get_cache()
    cache_key = compute_cache_key(tts_request)
    tts_engine = get_tts_engine()

    async with rate_limiter.acquire_concurrent(ctx):
        audio_bytes, srt_content = await tts_engine.synthesize_with_subtitles(
            text=text, voice=tts_request.voice,
            rate=tts_request.rate, pitch=tts_request.pitch,
            volume=tts_request.volume, words_per_cue=tts_request.words_per_cue,
        )
        cached_path = cache.put(cache_key, audio_bytes)

    rl_headers = rate_limiter.get_headers(ctx, usage)
    return JSONResponse({
        "srt": srt_content,
        "cache_key": cache_key[:16],
        "cache_hit": False,
    }, headers=rl_headers)
```

**File: `app/models/schemas.py`**:

```python
class TTSSubtitleRequest(TTSRequest):
    words_per_cue: int = Field(default=10, ge=1, le=50,
        description="Words per subtitle cue line")
```

### Frontend Changes
- Checkbox "Generate Subtitle (.srt)" di bawah Generate button di `index.html`
- Kalau checked → POST `/tts/subtitle` → receive JSON with `srt` field
- Show "Download SRT" button → Blob download as `.srt` file
- Audio tetap dari cache via normal `/tts` call (or serve from cache key)

### Testing Checklist
- [ ] SubMaker produces valid SRT format
- [ ] `words_per_cue` parameter works (1, 10, 50)
- [ ] SRT timing aligns with audio
- [ ] Download SRT button works in browser
- [ ] Rate limiting applies (same as /tts — uses check_and_consume)
- [ ] RequestContext works (anon + registered)
- [ ] Proxy retry + direct fallback pattern preserved

---

## F2: Voice Emotion/Style Control

### Why
Beberapa edge-tts voices support SSML `<mstts:express-as>` — emosi: cheerful, sad, angry, whispering, excited, dll.

### CRITICAL: Verification Gate

```python
# RUN THIS FIRST — blocks F2 + F7 implementation
import edge_tts, asyncio

async def test_ssml():
    ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">'
            '<voice name="en-US-AriaNeural">'
            '<mstts:express-as style="cheerful">'
            'Hello! This is a cheerful test!'
            '</mstts:express-as></voice></speak>')

    c = edge_tts.Communicate(text=ssml, voice="en-US-AriaNeural")
    audio = b""
    async for chunk in c.stream():
        if chunk["type"] == "audio": audio += chunk["data"]
    with open("test_ssml.mp3", "wb") as f: f.write(audio)
    print(f"OK: {len(audio)} bytes — listen to verify cheerful tone")

asyncio.run(test_ssml())
```

**If SSML NOT supported** → skip F2 + F7 entirely.

### Supported Voices (partial)

| Voice | Styles |
|-------|--------|
| en-US-AriaNeural | chat, cheerful, customerservice, empathetic, narration-professional, newscast-casual, newscast-formal, angry, sad, excited, friendly, terrified, shouting, unfriendly, whispering, hopeful |
| en-US-GuyNeural | newscast, angry, cheerful, sad, excited, friendly, terrified, shouting, unfriendly, whispering, hopeful |
| en-US-JennyNeural | assistant, chat, customerservice, newscast, angry, cheerful, sad, excited, friendly, terrified, shouting, unfriendly, whispering, hopeful |
| en-US-SaraNeural | angry, cheerful, sad, excited, friendly, terrified, shouting, unfriendly, whispering, hopeful |
| zh-CN-XiaoxiaoNeural | chat, customerservice, narration, newscast, affectionate, angry, calm, cheerful, disgruntled, fearful, gentle, lyrical, sad, serious, poetry-reading |

### Backend Changes

**File: `app/data/voice_styles.json`** (NEW) — registry voice → styles

**File: `app/services/tts_engine.py`** — tambah SSML builder + modify `_generate`:

```python
@staticmethod
def _escape_ssml(text: str) -> str:
    return (text.replace("&","&amp;").replace("<","&lt;")
            .replace(">","&gt;").replace('"',"&quot;").replace("'","&apos;"))

def _build_style_ssml(self, text, voice, style, style_degree=None) -> str:
    degree = f' styledegree="{style_degree}"' if style_degree else ''
    escaped = self._escape_ssml(text)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">'
        f'<voice name="{voice}">'
        f'<mstts:express-as style="{style}"{degree}>{escaped}</mstts:express-as>'
        '</voice></speak>'
    )
```

Modify `synthesize()` to accept `style` + `style_degree` params. If style set, wrap text in SSML before passing to `_generate()`.

**File: `app/models/schemas.py`** — extend TTSRequest:

```python
class TTSRequest(BaseModel):
    text: str = Field(...)
    voice: str = Field(default="id-ID-GadisNeural")
    rate: str = Field(default="+0%")
    pitch: str = Field(default="+0Hz")
    volume: str = Field(default="+0%")
    style: Optional[str] = Field(default=None,
        description="Voice emotion/style (cheerful, sad, whispering, etc.)")
    style_degree: Optional[float] = Field(default=None, ge=0.01, le=2.0,
        description="Style intensity 0.01-2.0")
```

**File: `app/api/v1/tts.py`** — update `compute_cache_key` to include style:

```python
def compute_cache_key(req: TTSRequest) -> str:
    data = {"text": req.text, "voice": req.voice, "rate": req.rate, "pitch": req.pitch}
    if req.style: data["style"] = req.style
    if req.style_degree: data["style_degree"] = req.style_degree
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
```

**File: `app/api/v1/voices.py`** — new endpoint:

```python
@router.get("/voices/styles")
async def get_voice_styles():
    """Get supported styles per voice."""
    return load_voice_styles()  # from voice_styles.json
```

### Frontend Changes
- Style dropdown (hidden by default, shown when voice supports styles)
- Style degree slider (0.01 — 2.0)
- Fetch `/voices/styles` once, cache in JS memory

### Testing Checklist
- [ ] SSML verification test passes (GATE)
- [ ] Voice with style → audible emotion change
- [ ] Voice without style → plain text (no SSML)
- [ ] Style dropdown hidden for unsupported voices
- [ ] Cache key includes style — different style = different cache
- [ ] Backward compatible — request without `style` works unchanged
- [ ] SSML escaping — text with `<`, `>`, `&` doesn't break

---

## F3: Voice Character Presets

### Why
1,200+ voices + sliders + styles = decision paralysis. Presets = pre-tuned starting points.

### Backend

**File: `app/data/presets.json`** (NEW):

```json
{
    "presets": [
        {"id":"news-anchor","name":"News Anchor","description":"Professional newscast, clear and authoritative",
         "voice":"en-US-GuyNeural","rate":"+5%","pitch":"+0Hz","volume":"+10%","style":"newscast","category":"professional"},
        {"id":"storyteller","name":"Storyteller","description":"Warm narrator for stories and audiobooks",
         "voice":"en-US-JennyNeural","rate":"-10%","pitch":"-2Hz","volume":"+0%","style":"chat","style_degree":1.2,"category":"creative"},
        {"id":"asmr","name":"ASMR / Whisper","description":"Soft whispering for ASMR content",
         "voice":"en-US-AriaNeural","rate":"-20%","pitch":"-3Hz","volume":"-10%","style":"whispering","style_degree":2.0,"category":"creative"},
        {"id":"hype-man","name":"Hype Man","description":"Excited, energetic for promos",
         "voice":"en-US-GuyNeural","rate":"+15%","pitch":"+5Hz","volume":"+20%","style":"excited","style_degree":1.8,"category":"creative"},
        {"id":"teacher","name":"Friendly Teacher","description":"Clear, patient for education",
         "voice":"en-US-SaraNeural","rate":"-5%","pitch":"+0Hz","volume":"+5%","style":"friendly","category":"professional"},
        {"id":"angry-rant","name":"Angry Rant","description":"Frustrated, dramatic",
         "voice":"en-US-GuyNeural","rate":"+10%","pitch":"+5Hz","volume":"+20%","style":"angry","style_degree":2.0,"category":"creative"},
        {"id":"sad-narrator","name":"Sad Narrator","description":"Melancholic, emotional readings",
         "voice":"en-US-AriaNeural","rate":"-15%","pitch":"-5Hz","volume":"-5%","style":"sad","style_degree":1.5,"category":"creative"},
        {"id":"indo-narrator","name":"Narator Indonesia","description":"Indonesian narrator, natural pace",
         "voice":"id-ID-GadisNeural","rate":"+0%","pitch":"+0Hz","volume":"+0%","style":null,"category":"regional"},
        {"id":"indo-formal","name":"MC Formal Indonesia","description":"Indonesian MC, clear diction",
         "voice":"id-ID-ArdiNeural","rate":"+10%","pitch":"+3Hz","volume":"+10%","style":null,"category":"regional"}
    ],
    "categories": [
        {"id":"professional","name":"Professional"},
        {"id":"creative","name":"Creative"},
        {"id":"regional","name":"Regional"}
    ]
}
```

**File: `app/api/v1/voices.py`**:

```python
@router.get("/voices/presets")
async def get_presets():
    return presets_data
```

### Frontend
- Preset cards grid (Tailwind: `grid grid-cols-2 md:grid-cols-4 gap-3`)
- Click preset → auto-fill voice, rate, pitch, volume, style
- Active card border accent (`border-emerald-500`)
- User can override settings after applying

### Effort: Low

---

## F4: Audio Waveform Visualizer

### Why
Replace progress bar with waveform visualization. 100% frontend — no backend changes.

### Implementation

**File: `app/static/js/waveform.js`** (NEW)

Uses Web Audio API `decodeAudioData` → compute amplitude per bar → draw on `<canvas>` with progress overlay. Green (`#10b981`) for played portion, dark for unplayed. `requestAnimationFrame` loop for real-time update. Click canvas → seek.

Fallback to simple progress bar if `AudioContext` unavailable.

### Effort: Medium (frontend only)

---

## F5: Multi-Voice Script Mode

### Why
Dialog/podcast with multiple voices in one audio file.

```
[Gadis] Selamat datang di podcast hari ini
[Ardi] Terima kasih sudah mengundang saya
[Gadis] Topik kita hari ini tentang AI
```

### New Dependency

```
pydub==0.25.1
```

Dockerfile: `RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*`

### Backend

**File: `app/services/script_service.py`** (NEW):

```python
def parse_script(raw: str) -> list[ScriptLine]:
    """Parse [Speaker] text format. Lines without tag inherit previous speaker."""

async def generate_script_audio(lines, voice_map, pause_ms=500) -> bytes:
    """Sequential TTS per line → pydub merge with pauses → MP3 bytes."""
    tts = get_tts_engine()
    segments = []
    for line in lines:
        voice = voice_map.get(line.speaker, line.speaker)
        audio = await tts.synthesize(text=line.text, voice=voice)
        segments.append(AudioSegment.from_mp3(io.BytesIO(audio)))
    merged = segments[0]
    for seg in segments[1:]:
        merged += AudioSegment.silent(duration=pause_ms) + seg
    output = io.BytesIO()
    merged.export(output, format="mp3", bitrate="48k")
    return output.getvalue()
```

**File: `app/api/v1/tts.py`**:

```python
@router.post("/tts/script")
async def generate_script(
    request: ScriptRequest,
    ctx: RequestContext = Depends(resolve_request_context),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    lines = parse_script(request.script)
    total_chars = sum(len(l.text) for l in lines)
    usage = await rate_limiter.check_and_consume(ctx, db, total_chars)
    async with rate_limiter.acquire_concurrent(ctx):
        audio = await generate_script_audio(lines, request.voice_map, request.pause_ms)
    return Response(content=audio, media_type="audio/mpeg",
                    headers=rate_limiter.get_headers(ctx, usage))
```

**File: `app/models/schemas.py`**:

```python
class ScriptRequest(BaseModel):
    script: str = Field(..., min_length=1, max_length=50000)
    voice_map: dict[str, str] = Field(default_factory=dict)
    pause_ms: int = Field(default=500, ge=0, le=3000)
```

### Frontend
- Mode tabs: Simple | Script Mode | Compare
- Script textarea with `[Speaker] text` placeholder
- Auto-detect speakers → render voice dropdown per speaker
- Pause slider (0-3000ms)
- Max 50 lines enforced

### Effort: Medium-High

---

## F6: Voice Comparison Tool

No new backend. Frontend sends parallel `/tts` requests.

- 2-4 voice selector slots
- One text input, generate all voices simultaneously
- Side-by-side mini players (play one at a time)
- Each slot: voice dropdown + play/pause button

### Rate Limit Note
Each comparison voice = 1 TTS request. A 3-voice compare costs 3 daily requests. Document this in UI.

### Effort: Medium (frontend only)

---

## F7: Pronunciation Editor

Depends on F2 SSML verification. Uses `<sub>` tag:

```xml
<sub alias="engine-x">nginx</sub> is fast.
```

**Schema change**:
```python
class TTSRequest(BaseModel):
    # ... existing
    pronunciations: Optional[dict[str, str]] = Field(default=None)
```

Backend pre-processes text: replace words with `<sub>` tags → wrap in `<speak>` → send to edge-tts.

Frontend: click word → popup "How to pronounce?" → save in localStorage.

### Effort: Medium (depends on F2 gate)

---

## F8: Embeddable Widget

New endpoint + mini HTML player.

```python
@router.get("/embed")
async def embed_player(text: str = Query(..., max_length=500), voice: str = Query(default="id-ID-GadisNeural")):
    return HTMLResponse(embed_template.format(text=escape(text), voice=voice))
```

- Anonymous rate limit applies (5/day per IP)
- Max 500 chars
- eidosSpeech branding watermark
- Embed code: `<iframe src="https://eidosspeech.xyz/embed?text=...&voice=..." width="400" height="80">`

### Effort: Medium

---

## F9: Voice Favorites

100% frontend. localStorage array of voice short names. Star icon toggle. "Favorites" filter button alongside All/Male/Female. Zero backend.

### Effort: Low

---

## F10: Keyboard Shortcuts

100% frontend.

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Generate audio |
| `Space` (not in input) | Play/Pause |
| `Ctrl+S` | Download MP3 |
| `Ctrl+Shift+S` | Download SRT (if available) |
| `Escape` | Stop playback |

Help icon → shortcuts modal.

### Effort: Low

---

## Implementation Phases

### Phase A: Quick Wins — No new deps, no backend risk
**Features**: F3 (Presets), F9 (Favorites), F10 (Shortcuts), F4 (Waveform)
**Effort**: ~2-3 days
**Risk**: Zero

```
F3  → presets.json + GET /voices/presets + frontend cards
F9  → favorites.js (localStorage only)
F10 → shortcuts.js (keyboard events only)
F4  → waveform.js (Web Audio API canvas)
```

### Phase B: Core Differentiators — Backend changes, edge-tts native
**Features**: F1 (SRT/Subtitle), F2 (Voice Styles), F7 (Pronunciation)
**Effort**: ~3-5 days
**GATE**: Run SSML verification test (blocks F2 + F7, NOT F1)

```
Step 1: F1 SRT → SubMaker integration (no SSML dependency, always safe)
Step 2: Run SSML test script
Step 3: If SSML pass → F2 Voice Styles + F7 Pronunciation
Step 4: If SSML fail → skip F2/F7, ship F1 only
```

### Phase C: Advanced Features — New dependency (pydub + ffmpeg)
**Features**: F5 (Multi-Voice Script), F6 (Voice Compare)
**Effort**: ~3-5 days

```
F5 → pydub install + Dockerfile ffmpeg + script_service.py + endpoint + UI
F6 → pure frontend (parallel /tts + multi-player)
```

### Phase D: Platform — Growth
**Features**: F8 (Embeddable Widget)
**Effort**: ~2-3 days

```
F8 → /embed endpoint + mini player HTML + anonymous rate limit
```

---

## File Changes Summary

### New Files

| File | Feature | Type |
|------|---------|------|
| `app/data/voice_styles.json` | F2 | Config |
| `app/data/presets.json` | F3 | Config |
| `app/services/script_service.py` | F5 | Backend |
| `app/static/js/waveform.js` | F4 | Frontend |
| `app/static/js/script-mode.js` | F5 | Frontend |
| `app/static/js/compare-mode.js` | F6 | Frontend |
| `app/static/js/favorites.js` | F9 | Frontend |
| `app/static/js/shortcuts.js` | F10 | Frontend |

### Modified Files

| File | Features | Changes |
|------|----------|---------|
| `app/services/tts_engine.py` | F1, F2, F7 | `synthesize_with_subtitles()`, `_build_style_ssml()`, `_escape_ssml()` |
| `app/api/v1/tts.py` | F1, F5 | `/tts/subtitle`, `/tts/script` endpoints |
| `app/api/v1/voices.py` | F2, F3 | `/voices/styles`, `/voices/presets` endpoints |
| `app/models/schemas.py` | F1, F2, F5, F7 | `TTSSubtitleRequest`, `ScriptRequest`, style/pronunciation fields |
| `app/static/index.html` | ALL | Mode tabs, presets, style controls, waveform, script editor |
| `app/static/js/api-client.js` | F1, F2, F3, F5 | New API methods |
| `requirements.txt` | F5 | `pydub==0.25.1` |
| `Dockerfile` | F5 | `ffmpeg` install |

### New Endpoints

| Method | Path | Feature | Auth |
|--------|------|---------|------|
| POST | `/api/v1/tts/subtitle` | F1 | API Key / JWT |
| GET | `/api/v1/voices/styles` | F2 | None |
| GET | `/api/v1/voices/presets` | F3 | None |
| POST | `/api/v1/tts/script` | F5 | API Key / JWT |
| GET | `/embed` | F8 | None (rate limited) |

---

## Backward Compatibility

Semua fitur **additive** — zero breaking changes:

1. **Existing endpoints untouched** — `/tts`, `/voices`, `/auth/*`, `/admin/*` unchanged
2. **Schema backward compatible** — new fields all `Optional` with default `None`
3. **Auth unchanged** — RequestContext + RateLimiter flow identical
4. **Cache compatible** — new fields in cache key only when non-null (existing keys unaffected)
5. **DB unchanged** — no new tables (features are stateless or localStorage)
6. **Frontend progressive** — tab-based, Simple mode default
7. **Docker compatible** — only F5 adds ffmpeg (optional phase)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| edge-tts SSML not supported | F2 + F7 blocked | Test first (Phase B gate). F1 unaffected |
| SubMaker timing inaccurate | F1 quality | Accept imperfect, document limitation |
| pydub + ffmpeg Docker size | +100MB image | Phase C optional, can defer |
| SSML injection via user text | Security | `_escape_ssml()` escapes all XML chars |
| Parallel compare hits rate limit | F6 UX | Document: each voice = 1 request |
| UI clutter from many modes | UX confusion | Tab-based, Simple default |
| Multiple JS files load time | Performance | Lazy-load per mode tab |

---

## Success Metrics

| Feature | Success Indicator |
|---------|-------------------|
| F1 SRT | >10% of generations include SRT download |
| F2 Styles | Style dropdown used in >20% of en-US voice generations |
| F3 Presets | >30% of first-time users click a preset |
| F4 Waveform | Expected polish — no metric needed |
| F5 Script | Power users generate multi-voice scripts |
| F6 Compare | Users compare 2+ voices per session |
| F7 Pronunciation | Users save custom pronunciations |
| F8 Embed | External sites embed eidosSpeech player |
| F9 Favorites | Users bookmark 3+ voices |
| F10 Shortcuts | Power users use Ctrl+Enter consistently |
