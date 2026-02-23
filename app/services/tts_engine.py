"""
eidosSpeech v2 — TTS Engine
Wraps edge-tts with proxy support, retry logic, and fallback to direct connection.

Fallback strategy:
  1. Attempt with proxy (from ProxyManager round-robin)
  2. If proxy fails 3 times → ProxyManager marks it dead, returns None
  3. Next attempt uses direct connection (VPS IP)
  4. If all proxies are dead → always direct connection

This means: proxy mati = tetap jalan via direct connection VPS.
"""

import asyncio
import logging

import edge_tts

from app.config import settings
from app.services.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Wraps edge-tts with:
    - Optional proxy rotation via ProxyManager
    - Retry logic (3 attempts, exponential backoff)
    - Automatic fallback to direct connection if all proxies fail
    - SSML support for voice styles and pronunciation
    - Returns raw MP3 bytes
    """

    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager

    @staticmethod
    def _escape_ssml(text: str) -> str:
        """Escape special XML characters for SSML"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _build_style_ssml(
        self, text: str, voice: str, style: str, style_degree: float | None = None
    ) -> str:
        """Build SSML with express-as style tag"""
        degree_attr = f' styledegree="{style_degree}"' if style_degree else ""
        escaped_text = self._escape_ssml(text)
        
        return (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">'
            f'<voice name="{voice}">'
            f'<mstts:express-as style="{style}"{degree_attr}>'
            f'{escaped_text}'
            '</mstts:express-as>'
            '</voice>'
            '</speak>'
        )

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        style: str | None = None,
        style_degree: float | None = None,
    ) -> bytes:
        """
        Generate TTS audio. Returns MP3 bytes.

        Retry flow per attempt:
          - Ask ProxyManager for next healthy proxy
          - If proxy fails → mark failure, ProxyManager may disable it
          - ProxyManager returns None when all proxies are dead → use direct
          - So even if proxies are configured but all down, we still work

        Raises RuntimeError only if ALL attempts with both proxy and direct fail.
        """
        last_error = None
        tried_direct = False  # Ensure we always try direct if proxy keeps failing
        
        max_retries = settings.tts_max_retries
        retry_delay = settings.tts_retry_delay

        for attempt in range(1, max_retries + 1):
            # ProxyManager returns None when: no proxy configured OR all proxies dead
            proxy_url = await self.proxy_manager.get_next()

            # On last attempt, force direct connection as final safety net
            # This handles the case where ProxyManager still returns a proxy
            # but it keeps failing — we override to direct on final try
            if attempt == max_retries and proxy_url and not tried_direct:
                logger.info("TTS_DIRECT_FALLBACK forcing direct connection on final attempt")
                proxy_url = None
                tried_direct = True

            try:
                audio = await self._generate(text, voice, rate, pitch, volume, proxy_url, style, style_degree)

                if proxy_url:
                    await self.proxy_manager.mark_success(proxy_url)

                logger.info(
                    f"TTS_SUCCESS voice={voice} chars={len(text)} "
                    f"via={'proxy' if proxy_url else 'direct'} attempt={attempt}"
                )
                return audio

            except Exception as e:
                last_error = e
                via = proxy_url if proxy_url else "direct"
                logger.warning(
                    f"TTS_FAIL attempt={attempt}/{max_retries} "
                    f"voice={voice} via={via} error={e}"
                )

                if proxy_url:
                    await self.proxy_manager.mark_failure(proxy_url)

                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)  # 1s, 2s, ...

        raise RuntimeError(
            f"TTS generation failed after {max_retries} attempts "
            f"(tried proxy + direct fallback): {last_error}"
        )

    async def synthesize_with_subtitles(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        words_per_cue: int = 10,
        style: str | None = None,
        style_degree: float | None = None,
    ) -> tuple[bytes, str]:
        """
        Generate TTS audio + SRT subtitle. Returns (mp3_bytes, srt_string).
        Uses edge-tts SubMaker for word-level timing.
        """
        last_error = None
        tried_direct = False
        
        max_retries = settings.tts_max_retries
        retry_delay = settings.tts_retry_delay

        for attempt in range(1, max_retries + 1):
            proxy_url = await self.proxy_manager.get_next()

            if attempt == max_retries and proxy_url and not tried_direct:
                logger.info("TTS_SRT_DIRECT_FALLBACK forcing direct on final attempt")
                proxy_url = None
                tried_direct = True

            try:
                audio, srt = await self._generate_with_subs(
                    text, voice, rate, pitch, volume, proxy_url, words_per_cue, style, style_degree
                )

                if proxy_url:
                    await self.proxy_manager.mark_success(proxy_url)

                logger.info(
                    f"TTS_SRT_SUCCESS voice={voice} chars={len(text)} "
                    f"via={'proxy' if proxy_url else 'direct'} attempt={attempt}"
                )
                return audio, srt

            except Exception as e:
                last_error = e
                via = proxy_url if proxy_url else "direct"
                logger.warning(
                    f"TTS_SRT_FAIL attempt={attempt}/{max_retries} "
                    f"voice={voice} via={via} error={e}"
                )

                if proxy_url:
                    await self.proxy_manager.mark_failure(proxy_url)

                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)

        raise RuntimeError(
            f"TTS+SRT generation failed after {max_retries} attempts: {last_error}"
        )

    async def _generate(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
        proxy: str | None,
        style: str | None = None,
        style_degree: float | None = None,
    ) -> bytes:
        """Single TTS generation attempt via edge-tts"""
        # If style is provided, wrap text in SSML
        if style:
            text = self._build_style_ssml(text, voice, style, style_degree)
        
        kwargs = {
            "text": text,
            "voice": voice,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
        }

        if proxy:
            kwargs["proxy"] = proxy

        communicate = edge_tts.Communicate(**kwargs)

        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            raise RuntimeError("No audio data received from TTS engine")

        return b"".join(audio_chunks)

    async def _generate_with_subs(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
        proxy: str | None,
        words_per_cue: int,
        style: str | None = None,
        style_degree: float | None = None,
    ) -> tuple[bytes, str]:
        """Single TTS+SRT generation attempt via edge-tts with SubMaker"""
        # If style is provided, wrap text in SSML
        if style:
            text = self._build_style_ssml(text, voice, style, style_degree)
        
        kwargs = {
            "text": text,
            "voice": voice,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
        }

        if proxy:
            kwargs["proxy"] = proxy

        communicate = edge_tts.Communicate(**kwargs)
        submaker = edge_tts.SubMaker()
        audio_chunks = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub(
                    (chunk["offset"], chunk["duration"]),
                    chunk["text"]
                )

        if not audio_chunks:
            raise RuntimeError("No audio data received from TTS engine")

        audio_bytes = b"".join(audio_chunks)
        srt_content = submaker.generate_subs(words_per_cue)

        return audio_bytes, srt_content


# ── Singleton ─────────────────────────────────────────────────────────────────
_tts_engine: TTSEngine = None


def get_tts_engine() -> TTSEngine:
    global _tts_engine
    if _tts_engine is None:
        from app.services.proxy_manager import get_proxy_manager
        _tts_engine = TTSEngine(get_proxy_manager())
    return _tts_engine


def init_tts_engine(proxy_manager: ProxyManager) -> TTSEngine:
    global _tts_engine
    _tts_engine = TTSEngine(proxy_manager)
    return _tts_engine
