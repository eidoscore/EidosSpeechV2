# eidosSpeech v2 - Feature Roadmap & Improvements

## 📋 Executive Summary

This document outlines actionable improvements and new features for eidosSpeech v2, prioritized by effort vs impact ratio. Based on current infrastructure analysis and competitive landscape.

**Current Stack:**
- Edge-TTS for voice synthesis
- Faster-Whisper for subtitle generation
- Semaphore (3 concurrent processes)
- SQLite database
- FastAPI backend
- File-based caching

---

## 🎯 PRIORITY 1: QUICK WINS (Week 1-4)
*Low effort, high impact - implement these first*

### 1.1 Response Caching System ⚡
**Status:** Partially implemented (file cache exists)
**Effort:** Low | **Impact:** High

**Current State:**
```python
# app/services/tts_engine.py already has file caching
cache_key = hashlib.sha256(f"{text}{voice_name}{rate}{pitch}{volume}".encode()).hexdigest()
```

**Improvements Needed:**
- ✅ Already caching audio files
- ❌ Add cache hit/miss metrics
- ❌ Add cache warming for popular voices
- ❌ Add cache headers in API response

**Implementation:**
```python
# Add to response headers
response.headers["X-Cache-Status"] = "HIT" if from_cache else "MISS"
response.headers["X-Cache-Key"] = cache_key[:16]
```

**Benefits:**
- 50-70% reduction in server load
- Instant response for repeated requests
- Better user experience
- Lower infrastructure costs

---

### 1.2 Queue Status Endpoint 📊
**Status:** Not implemented
**Effort:** Low | **Impact:** High

**Why:** Users currently don't know their position in queue (Semaphore limit = 3)

**Implementation:**
```python
# New endpoint: GET /api/v1/queue/status
@router.get("/queue/status")
async def get_queue_status():
    return {
        "available_slots": semaphore._value,
        "max_slots": 3,
        "current_load": f"{((3 - semaphore._value) / 3) * 100:.0f}%",
        "estimated_wait": "5-15 seconds" if semaphore._value == 0 else "instant"
    }
```

**Benefits:**
- Transparency for users
- Better UX during peak times
- Reduces support questions

---

### 1.3 Webhook Callback Support 🔔
**Status:** Not implemented
**Effort:** Medium | **Impact:** High

**Why:** For long scripts, users shouldn't need to poll

**Implementation:**
```python
# Add to TTS request
class TTSRequest(BaseModel):
    text: str
    voice: str
    webhook_url: Optional[str] = None  # NEW
    
# After generation completes
if request.webhook_url:
    async with httpx.AsyncClient() as client:
        await client.post(request.webhook_url, json={
            "status": "completed",
            "audio_url": audio_url,
            "request_id": request_id
        })
```

**Benefits:**
- Better for async workflows
- Enables automation
- Professional API experience

---

### 1.4 Audio Format Options 🎵
**Status:** MP3 only
**Effort:** Low | **Impact:** Medium

**Current:** Only MP3 output
**Proposed:** Support multiple formats

**Implementation:**
```python
# Add to request
class TTSRequest(BaseModel):
    format: str = "mp3"  # mp3, wav, ogg, flac
    bitrate: str = "128k"  # 64k, 128k, 192k, 256k, 320k

# Use ffmpeg for conversion (already installed)
if format != "mp3":
    subprocess.run([
        "ffmpeg", "-i", mp3_file,
        "-b:a", bitrate,
        output_file
    ])
```

**Benefits:**
- Flexibility for different use cases
- Competitive with paid services
- Better quality options

---

### 1.5 Batch Processing Endpoint 📦
**Status:** Not implemented
**Effort:** Medium | **Impact:** High

**Why:** Users often need multiple voices/texts

**Implementation:**
```python
# New endpoint: POST /api/v1/tts/batch
@router.post("/batch")
async def batch_tts(requests: List[TTSRequest]):
    results = []
    for req in requests:
        result = await generate_tts(req)
        results.append(result)
    return {"results": results, "count": len(results)}
```

**Benefits:**
- Reduces API calls
- Better for automation
- Efficient for multi-voice content

---

## 🔥 PRIORITY 2: MEDIUM EFFORT (Month 2-3)
*Medium effort, high impact - implement after quick wins*

### 2.1 Audio Post-Processing Options 🎚️
**Status:** Basic (rate, pitch, volume only)
**Effort:** Medium | **Impact:** High

**Current:** Only prosody adjustments
**Proposed:** Professional audio processing

**Implementation:**
```python
class AudioProcessing(BaseModel):
    normalize_volume: bool = False  # EBU R128 loudness
    noise_reduction: bool = False
    trim_silence: bool = False
    fade_in: float = 0.0  # seconds
    fade_out: float = 0.0
    
# Use ffmpeg filters
ffmpeg_filters = []
if normalize_volume:
    ffmpeg_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
if trim_silence:
    ffmpeg_filters.append("silenceremove=1:0:-50dB")
if fade_in > 0:
    ffmpeg_filters.append(f"afade=t=in:d={fade_in}")
```

**Benefits:**
- Professional audio quality
- Consistent volume across content
- Ready for production use

---

### 2.2 Background Music Mixing 🎼
**Status:** Not implemented
**Effort:** Medium | **Impact:** High

**Why:** Content creators need background music

**Implementation:**
```python
class TTSRequest(BaseModel):
    background_music: Optional[BackgroundMusic] = None
    
class BackgroundMusic(BaseModel):
    url: str
    volume: float = 0.3  # 30% of voice volume
    fade_in: float = 1.0
    fade_out: float = 1.0

# Use ffmpeg amerge
ffmpeg -i voice.mp3 -i music.mp3 \
  -filter_complex "[1:a]volume=0.3[music];[0:a][music]amerge=inputs=2[out]" \
  -map "[out]" output.mp3
```

**Benefits:**
- Professional content creation
- Unique selling point
- Higher perceived value

---

### 2.3 Full SSML Support 📝
**Status:** Partial (basic prosody only)
**Effort:** Medium | **Impact:** Medium

**Current:** Only rate, pitch, volume
**Proposed:** Full SSML spec

**Implementation:**
```python
# Already using Edge-TTS which supports SSML
# Just expose it in API

class TTSRequest(BaseModel):
    text: str
    use_ssml: bool = False  # NEW
    
if use_ssml:
    # Pass text directly to Edge-TTS as SSML
    ssml = text
else:
    # Wrap in SSML with prosody
    ssml = f"""<speak>
        <voice name="{voice}">
            <prosody rate="{rate}" pitch="{pitch}" volume="{volume}">
                {text}
            </prosody>
        </voice>
    </speak>"""
```

**Example SSML:**
```xml
<speak>
    <voice name="id-ID-GadisNeural">
        <prosody rate="fast" pitch="high">
            Hello <break time="500ms"/> World!
        </prosody>
    </voice>
    <voice name="id-ID-ArdiNeural">
        <emphasis level="strong">Welcome!</emphasis>
    </voice>
</speak>
```

**Benefits:**
- Advanced control for power users
- Better multi-voice support
- Industry standard

---

### 2.4 SRT to Speech (Batch Upload) 📄
**Status:** Not implemented
**Effort:** Medium | **Impact:** High

**Why:** Dubbing use case - huge market

**Implementation:**
```python
# New endpoint: POST /api/v1/tts/from-srt
@router.post("/from-srt")
async def srt_to_speech(
    srt_file: UploadFile,
    voice: str,
    output_format: str = "mp3"
):
    # Parse SRT
    subtitles = parse_srt(srt_file)
    
    # Generate audio for each subtitle
    audio_segments = []
    for sub in subtitles:
        audio = await generate_tts(sub.text, voice)
        audio_segments.append({
            "audio": audio,
            "start": sub.start,
            "end": sub.end
        })
    
    # Merge with silence padding
    final_audio = merge_audio_segments(audio_segments)
    
    return {"audio_url": final_audio}
```

**Benefits:**
- Killer feature for dubbing
- Unique in free TTS market
- High value for content creators

---

### 2.5 API Usage Analytics Dashboard 📊
**Status:** Basic (only daily counts)
**Effort:** Medium | **Impact:** Medium

**Current:** Only shows requests/chars used today
**Proposed:** Comprehensive analytics

**Implementation:**
```python
# New endpoint: GET /api/v1/analytics
@router.get("/analytics")
async def get_analytics(
    user: User = Depends(get_current_user),
    period: str = "7d"  # 7d, 30d, 90d
):
    return {
        "requests_chart": [...],  # Daily breakdown
        "most_used_voices": [...],
        "peak_hours": [...],
        "avg_chars_per_request": 450,
        "cache_hit_rate": "65%",
        "cost_projection": "$0 (free tier)"
    }
```

**Benefits:**
- Users can optimize usage
- Transparency builds trust
- Data for future pricing

---

## 🚀 PRIORITY 3: GAME CHANGERS (Month 4-6)
*High effort, massive impact - long-term competitive advantage*

### 3.1 Voice Cloning (Few-Shot) 🎤
**Status:** Not implemented
**Effort:** High | **Impact:** Massive

**Why:** Unique selling point, high demand

**Technical Approach:**
- Use Coqui TTS or RVC (Retrieval-based Voice Conversion)
- Requires GPU for training
- 15-60 seconds sample needed

**Implementation:**
```python
# New endpoint: POST /api/v1/voice/clone
@router.post("/voice/clone")
async def clone_voice(
    audio_file: UploadFile,
    voice_name: str,
    user: User = Depends(get_current_user)
):
    # Validate audio (15-60 seconds)
    # Extract voice features
    # Train model (queue job)
    # Save to user's custom voices
    
    return {
        "voice_id": "custom_voice_123",
        "status": "training",
        "eta": "5-10 minutes"
    }
```

**Challenges:**
- Requires GPU infrastructure
- Training time (5-10 min per voice)
- Storage for models
- Ethical concerns (voice consent)

**Benefits:**
- Massive competitive advantage
- Premium feature for monetization
- Viral potential

---

### 3.2 Real-Time Collaboration 👥
**Status:** Not implemented
**Effort:** High | **Impact:** High

**Why:** Target agencies/teams

**Features:**
- Shared voice library
- Team projects
- Role-based access
- Usage analytics per member
- Shared API keys

**Implementation:**
```python
# New models
class Team(Base):
    id: int
    name: str
    owner_id: int
    members: List[TeamMember]
    shared_voices: List[CustomVoice]
    
class TeamMember(Base):
    user_id: int
    team_id: int
    role: str  # owner, admin, member
    quota: int  # individual quota
```

**Benefits:**
- Higher pricing tier
- Sticky customers
- Enterprise market

---

### 3.3 Translate-on-the-fly 🌍
**Status:** Not implemented
**Effort:** High | **Impact:** High

**Why:** Expand to global market

**Implementation:**
```python
class TTSRequest(BaseModel):
    text: str
    source_lang: str = "auto"  # Auto-detect
    target_lang: str = "en"
    voice: str
    
# Use Google Translate API or LibreTranslate (free)
translated_text = translate(text, source_lang, target_lang)
audio = generate_tts(translated_text, voice)
```

**Benefits:**
- Global reach
- Unique feature
- High value for international creators

---

### 3.4 Integration Ecosystem 🔌
**Status:** Not implemented
**Effort:** High | **Impact:** High

**Pre-built Integrations:**
- ✅ Zapier/Make.com
- ✅ n8n (already mentioned)
- ✅ Google Sheets
- ✅ Notion
- ✅ Discord bot
- ✅ Telegram bot
- ✅ WordPress plugin

**Implementation:**
```python
# Create official integrations
# Publish to marketplaces
# Provide templates/examples
```

**Benefits:**
- Viral growth
- Network effects
- Lower barrier to entry

---

## 💰 PRIORITY 4: MONETIZATION (Optional)
*Sustainable business model while keeping free tier*

### 4.1 Tiered Pricing (Freemium) 💳

**Proposed Tiers:**

```
FREE (Current):
✅ 30 requests/day
✅ 2,000 chars/request (Web UI)
✅ 1,000 chars/request (API)
✅ Basic voices
✅ Standard queue
✅ MP3 output only

PRO ($5/month):
✅ 300 requests/day (10x)
✅ 10,000 chars/request
✅ Priority queue (skip Semaphore limit)
✅ All audio formats
✅ Background music mixing
✅ Voice cloning (5 custom voices)
✅ Webhook support
✅ Analytics dashboard
✅ Email support

TEAM ($20/month):
✅ 1,000 requests/day
✅ 50,000 chars/request
✅ Everything in PRO
✅ Team collaboration
✅ Shared voice library
✅ Role-based access
✅ Priority support
✅ Custom branding

ENTERPRISE (Custom):
✅ Unlimited requests
✅ Dedicated infrastructure
✅ SLA guarantee
✅ Custom voices
✅ White-label option
✅ On-premise deployment
```

**Implementation:**
```python
# Add to User model
class User(Base):
    tier: str = "free"  # free, pro, team, enterprise
    tier_expires: datetime = None
    
# Middleware to check tier
@app.middleware("http")
async def check_tier_limits(request: Request, call_next):
    user = get_user_from_token(request)
    if user.tier == "free" and user.requests_today >= 30:
        raise HTTPException(429, "Free tier limit reached")
    # ... etc
```

---

### 4.2 Pay-As-You-Go 💵

**Pricing:**
- $0.50 per 1,000 requests
- Or Rp 5,000 per 10,000 requests
- Top-up credit system
- No subscription

**Implementation:**
```python
class User(Base):
    credit_balance: float = 0.0  # USD
    
# Deduct on each request
if user.tier == "payg":
    cost = 0.0005  # $0.50 per 1000 = $0.0005 per request
    if user.credit_balance < cost:
        raise HTTPException(402, "Insufficient credit")
    user.credit_balance -= cost
```

**Benefits:**
- Flexible for casual users
- Predictable revenue
- No commitment

---

### 4.3 Bring Your Own Key (BYOK) 🔑

**Why:** Users with Azure/AWS accounts can use their own credits

**Implementation:**
```python
class User(Base):
    azure_api_key: Optional[str] = None
    azure_region: Optional[str] = None
    
# If user has BYOK, use their key
if user.azure_api_key:
    # Use user's Azure key
    # Charge management fee only ($0.10 per 1000 requests)
else:
    # Use eidosSpeech's infrastructure
```

**Benefits:**
- Heavy users can scale
- Lower cost for eidosSpeech
- Flexibility

---

## 🛠️ PRIORITY 5: DEVELOPER EXPERIENCE
*Make it easy for developers to integrate*

### 5.1 Official SDK Libraries 📚

**Languages:**
- Python: `pip install eidosspeech`
- Node.js: `npm install eidosspeech`
- PHP: `composer require eidosspeech/sdk`
- Go: `go get github.com/eidosspeech/go-sdk`
- Ruby: `gem install eidosspeech`

**Example (Python):**
```python
from eidosspeech import EidosSpeech

client = EidosSpeech(api_key="esk_...")

# Simple usage
audio = client.tts.generate(
    text="Hello world",
    voice="en-US-JennyNeural"
)
audio.save("output.mp3")

# Advanced usage
audio = client.tts.generate(
    text="Hello world",
    voice="en-US-JennyNeural",
    rate="+10%",
    pitch="+5Hz",
    format="wav",
    bitrate="192k",
    background_music={
        "url": "https://...",
        "volume": 0.3
    }
)
```

**Benefits:**
- Lower barrier to entry
- Better developer experience
- Faster adoption

---

### 5.2 Public API Status Page 📡

**URL:** `status.eidosspeech.xyz`

**Features:**
- Real-time uptime monitoring
- Response time graphs
- Incident history
- Scheduled maintenance
- Subscribe to updates

**Implementation:**
- Use Uptime Robot (free)
- Or StatusPage.io
- Or self-hosted (Cachet)

**Benefits:**
- Transparency
- Trust building
- Professional image

---

### 5.3 Changelog & Roadmap 🗺️

**URL:** `roadmap.eidosspeech.xyz`

**Features:**
- What's new (changelog)
- Upcoming features
- Voting system (user feedback)
- Release notes
- Breaking changes

**Implementation:**
- Use Canny.io (free tier)
- Or ProductBoard
- Or self-hosted (Fider)

**Benefits:**
- Community engagement
- User retention
- Feedback loop
- Transparency

---

## 📅 IMPLEMENTATION ROADMAP

### Month 1-2: Quick Wins 🎯
**Goal:** Improve current experience, low-hanging fruit

**Week 1-2:**
- ✅ Cache metrics & headers
- ✅ Queue status endpoint
- ✅ Audio format options

**Week 3-4:**
- ✅ Webhook callback support
- ✅ Batch processing endpoint
- ✅ Documentation updates

**Expected Impact:**
- 50% reduction in server load
- Better UX during peak times
- More professional API

---

### Month 3-4: Medium Impact 🔥
**Goal:** Add competitive features

**Week 5-8:**
- ✅ Audio post-processing (normalize, fade, trim)
- ✅ Background music mixing
- ✅ Full SSML support
- ✅ SRT to speech

**Week 9-12:**
- ✅ Analytics dashboard
- ✅ SDK libraries (Python, Node.js)
- ✅ Status page
- ✅ Changelog/Roadmap

**Expected Impact:**
- Competitive with paid services
- Better developer experience
- Professional image

---

### Month 5-6: Game Changers 🚀
**Goal:** Unique selling points

**Week 13-18:**
- ✅ Voice cloning (MVP)
- ✅ Translate-on-the-fly
- ✅ Team collaboration features

**Week 19-24:**
- ✅ Integration ecosystem (Zapier, etc.)
- ✅ Premium tier launch
- ✅ Marketing push

**Expected Impact:**
- Viral potential
- Revenue generation
- Market leadership

---

## 🎯 SUCCESS METRICS

### Technical Metrics:
- **Cache Hit Rate:** Target 60%+
- **API Response Time:** <500ms (p95)
- **Uptime:** 99.5%+
- **Error Rate:** <1%

### Business Metrics:
- **Daily Active Users:** 100 → 500 (Month 3)
- **API Requests/Day:** 1,000 → 10,000 (Month 6)
- **Conversion to Paid:** 2-5% (Month 6)
- **MRR:** $0 → $500 (Month 6)

### User Metrics:
- **NPS Score:** Target 50+
- **Retention (7-day):** Target 40%+
- **Avg Session Duration:** Target 5+ min
- **Feature Adoption:** 30%+ use new features

---

## 🚨 RISKS & MITIGATION

### Technical Risks:

**1. Infrastructure Scaling**
- **Risk:** Current Semaphore (3 concurrent) won't scale
- **Mitigation:** 
  - Implement queue system (Celery + Redis)
  - Add horizontal scaling
  - Consider serverless for TTS generation

**2. Voice Cloning Ethics**
- **Risk:** Misuse for deepfakes, scams
- **Mitigation:**
  - Require voice consent verification
  - Watermark cloned voices
  - Terms of service enforcement
  - Report abuse system

**3. Cost Explosion**
- **Risk:** Free tier abuse, high infrastructure costs
- **Mitigation:**
  - Rate limiting per IP
  - Cloudflare bot protection
  - Monitor usage patterns
  - Implement soft limits

### Business Risks:

**1. Monetization Backlash**
- **Risk:** Users angry about paid tiers
- **Mitigation:**
  - Keep free tier generous
  - Grandfather existing users
  - Transparent communication
  - Value-based pricing

**2. Competition**
- **Risk:** Big players (ElevenLabs, Play.ht) add free tier
- **Mitigation:**
  - Focus on unique features (voice cloning, SRT)
  - Build community
  - Fast iteration
  - Developer-first approach

---

## 💡 FINAL RECOMMENDATIONS

### Do First (Month 1):
1. ✅ Queue status endpoint
2. ✅ Webhook callbacks
3. ✅ Audio format options
4. ✅ Cache improvements

### Do Next (Month 2-3):
1. ✅ Audio post-processing
2. ✅ Background music
3. ✅ SRT to speech
4. ✅ Analytics dashboard

### Do Later (Month 4-6):
1. ✅ Voice cloning
2. ✅ Team features
3. ✅ Premium tiers
4. ✅ Integration ecosystem

### Don't Do (Yet):
- ❌ Mobile apps (focus on API first)
- ❌ Video generation (out of scope)
- ❌ Live streaming TTS (too complex)
- ❌ On-premise deployment (not ready)

---

## 📞 NEXT STEPS

1. **Review this document** with team
2. **Prioritize features** based on resources
3. **Create GitHub issues** for each feature
4. **Set up project board** (Kanban)
5. **Start with Quick Wins** (Month 1)
6. **Gather user feedback** continuously
7. **Iterate fast** based on data

---

**Document Version:** 1.0
**Last Updated:** February 26, 2026
**Author:** AI Analysis + User Feedback
**Status:** Draft for Review

---

## 📚 APPENDIX

### A. Competitive Analysis

**ElevenLabs:**
- ✅ Best voice quality
- ✅ Voice cloning
- ❌ Expensive ($5-99/month)
- ❌ Limited free tier (10k chars/month)

**Play.ht:**
- ✅ Good quality
- ✅ Many voices
- ❌ Expensive ($19-99/month)
- ❌ Complex pricing

**Murf.ai:**
- ✅ Professional features
- ✅ Video sync
- ❌ Very expensive ($29-99/month)
- ❌ No free tier

**eidosSpeech Advantage:**
- ✅ Truly free (30 req/day)
- ✅ 1,200+ voices
- ✅ Simple API
- ✅ No credit card required
- ❌ Voice quality (Edge-TTS vs custom models)

### B. Technology Stack Recommendations

**Current:**
- FastAPI ✅
- SQLite ✅ (for now)
- Edge-TTS ✅
- Faster-Whisper ✅

**Recommended Additions:**
- Redis (caching, queue)
- Celery (background jobs)
- PostgreSQL (when scaling)
- S3/R2 (audio storage)
- Sentry (error tracking)
- Prometheus (metrics)

### C. Cost Projections

**Current (Free Tier Only):**
- Server: $20/month (VPS)
- Domain: $12/year
- Total: ~$25/month

**With 1,000 DAU:**
- Server: $100/month (upgraded VPS)
- CDN: $20/month
- Storage: $10/month
- Total: ~$130/month

**With 10,000 DAU:**
- Servers: $500/month (multiple instances)
- CDN: $100/month
- Storage: $50/month
- Database: $50/month
- Total: ~$700/month

**Revenue Needed (Break-even):**
- 1,000 DAU: 140 paid users @ $5/month
- 10,000 DAU: 140 paid users @ $5/month (2% conversion)

### D. Marketing Strategy

**Phase 1 (Month 1-2):**
- Reddit posts (r/SideProject, r/webdev)
- Product Hunt launch
- Dev.to articles
- Twitter/X threads

**Phase 2 (Month 3-4):**
- YouTube tutorials
- Integration showcases
- Case studies
- Influencer partnerships

**Phase 3 (Month 5-6):**
- Paid ads (Google, Facebook)
- Affiliate program
- Conference talks
- Press releases

---

**End of Document**
