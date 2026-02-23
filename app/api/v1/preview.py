"""
eidosSpeech v2 — Voice Preview Endpoint
Generate and serve voice preview samples without consuming user quota.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import edge_tts
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

PREVIEW_DIR = Path("app/static/previews")
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

# Sample texts by language - GenZ style with eidosSpeech branding
SAMPLE_TEXTS = {
    'en': 'Yo! This is eidosSpeech. Free TTS, no cap!',
    'id': 'Halo! Ini eidosSpeech. TTS gratis, gak pake ribet!',
    'es': '¡Hola! Soy eidosSpeech. TTS gratis, sin complicaciones!',
    'fr': 'Salut! C\'est eidosSpeech. TTS gratuit, sans prise de tête!',
    'de': 'Hey! Das ist eidosSpeech. Kostenlos TTS, unkompliziert!',
    'ja': 'よっ！eidosSpeechだよ。無料TTS、マジ便利！',
    'zh': '嘿！这是eidosSpeech。免费TTS，超简单！',
    'ko': '안녕! eidosSpeech야. 무료 TTS, 완전 쉬워!',
    'pt': 'E aí! É o eidosSpeech. TTS grátis, sem enrolação!',
    'ru': 'Привет! Это eidosSpeech. Бесплатный TTS, без заморочек!',
    'ar': 'مرحبا! هذا eidosSpeech. TTS مجاني، بدون تعقيد!',
    'hi': 'हेलो! यह eidosSpeech है। मुफ्त TTS, बिल्कुल आसान!',
    'it': 'Ciao! Sono eidosSpeech. TTS gratis, senza complicazioni!',
    'nl': 'Hoi! Dit is eidosSpeech. Gratis TTS, geen gedoe!',
    'pl': 'Cześć! To eidosSpeech. Darmowy TTS, bez komplikacji!',
    'tr': 'Selam! Bu eidosSpeech. Ücretsiz TTS, kolay peasy!',
    'vi': 'Chào! Đây là eidosSpeech. TTS miễn phí, dễ xài!',
    'th': 'หวัดดี! นี่คือ eidosSpeech TTS ฟรี ใช้ง่ายมาก!',
}

# Lock to prevent concurrent generation of same preview
_generation_locks = {}


async def generate_preview(voice_id: str, language_code: str) -> Path:
    """Generate preview audio for a voice"""
    # Get sample text based on language
    lang = language_code.split('-')[0] if language_code else 'en'
    text = SAMPLE_TEXTS.get(lang, SAMPLE_TEXTS['en'])
    
    # Generate filename
    filename = f"{voice_id}.mp3"
    filepath = PREVIEW_DIR / filename
    
    # Generate audio
    communicate = edge_tts.Communicate(text, voice_id)
    await communicate.save(str(filepath))
    
    logger.info(f"PREVIEW_GENERATED voice={voice_id}")
    return filepath


@router.get("/preview/{voice_id}", include_in_schema=False)
async def get_voice_preview(voice_id: str):
    """
    Get voice preview sample. 
    Generates on first request, then serves from cache.
    Does NOT consume user quota.
    """
    try:
        # Check if preview already exists
        filepath = PREVIEW_DIR / f"{voice_id}.mp3"
        
        if filepath.exists():
            logger.debug(f"PREVIEW_CACHE_HIT voice={voice_id}")
            return FileResponse(
                str(filepath),
                media_type="audio/mpeg",
                headers={
                    "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
                    "X-Preview": "cached"
                }
            )
        
        # Preview doesn't exist, generate it
        # Use lock to prevent concurrent generation
        if voice_id not in _generation_locks:
            _generation_locks[voice_id] = asyncio.Lock()
        
        async with _generation_locks[voice_id]:
            # Double-check after acquiring lock
            if filepath.exists():
                logger.debug(f"PREVIEW_CACHE_HIT voice={voice_id} (after lock)")
                return FileResponse(
                    str(filepath),
                    media_type="audio/mpeg",
                    headers={
                        "Cache-Control": "public, max-age=31536000",
                        "X-Preview": "cached"
                    }
                )
            
            # Get voice info to determine language
            from app.services.voice_service import get_all_voices
            voices = await get_all_voices()
            voice = next((v for v in voices if v['id'] == voice_id), None)
            
            if not voice:
                raise HTTPException(status_code=404, detail="Voice not found")
            
            language_code = voice.get('language_code', 'en-US')
            
            # Generate preview
            filepath = await generate_preview(voice_id, language_code)
            
            return FileResponse(
                str(filepath),
                media_type="audio/mpeg",
                headers={
                    "Cache-Control": "public, max-age=31536000",
                    "X-Preview": "generated"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PREVIEW_ERROR voice={voice_id} error={e}")
        raise HTTPException(status_code=500, detail="Failed to generate preview")
