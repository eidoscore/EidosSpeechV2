"""
Generate voice preview samples for all voices.
Run this script to pre-generate preview audio files.
"""
import asyncio
import hashlib
from pathlib import Path
import edge_tts
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


async def generate_preview(voice_id: str, language_code: str) -> bool:
    """Generate preview audio for a voice"""
    try:
        # Get sample text based on language
        lang = language_code.split('-')[0] if language_code else 'en'
        text = SAMPLE_TEXTS.get(lang, SAMPLE_TEXTS['en'])
        
        # Generate filename (use hash for safety)
        filename = f"{voice_id}.mp3"
        filepath = PREVIEW_DIR / filename
        
        # Skip if already exists
        if filepath.exists():
            logger.debug(f"Preview already exists: {voice_id}")
            return True
        
        # Generate audio
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(filepath))
        
        logger.info(f"✓ Generated preview: {voice_id}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to generate preview for {voice_id}: {e}")
        return False


async def main():
    """Generate previews for all voices"""
    logger.info("Fetching voice list...")
    voices = await edge_tts.list_voices()
    
    logger.info(f"Found {len(voices)} voices")
    logger.info("Generating previews (this may take a while)...")
    
    tasks = []
    for voice in voices:
        voice_id = voice.get("ShortName", voice["Name"])
        language_code = voice.get("Locale", "")
        tasks.append(generate_preview(voice_id, language_code))
    
    # Generate in batches to avoid overwhelming the system
    batch_size = 10
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        results = await asyncio.gather(*batch, return_exceptions=True)
        
        # Log progress
        completed = i + len(batch)
        logger.info(f"Progress: {completed}/{len(tasks)} ({completed*100//len(tasks)}%)")
    
    logger.info(f"✓ Preview generation complete! Files saved to {PREVIEW_DIR}")
    logger.info(f"Total files: {len(list(PREVIEW_DIR.glob('*.mp3')))}")


if __name__ == "__main__":
    asyncio.run(main())
