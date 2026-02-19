"""
eidosSpeech v2 — Voice Service
Lists all available edge-tts voices and caches them in memory.
Supports Speechma-style 1,200+ voice count (multilingual × languages).
"""

import asyncio
import logging
from functools import lru_cache

import edge_tts

logger = logging.getLogger(__name__)

# Cache voice list in memory (loaded once on startup)
_voices_cache: list[dict] | None = None
_voices_lock = asyncio.Lock()


async def get_all_voices() -> list[dict]:
    """
    Get all edge-tts voices. Cached in memory after first call.
    Returns list of voice dicts with id, name, language, gender, etc.
    """
    global _voices_cache

    if _voices_cache is not None:
        return _voices_cache

    async with _voices_lock:
        if _voices_cache is not None:  # double-check after lock
            return _voices_cache

        try:
            voices = await edge_tts.list_voices()
            _voices_cache = [
                {
                    "id": v["Name"],
                    "name": v.get("FriendlyName", v["Name"].split("-")[-1].replace("Neural", "").strip()),
                    "language": v.get("LocaleName", ""),
                    "language_code": v.get("Locale", ""),
                    "gender": v.get("Gender", "Unknown"),
                    "is_multilingual": "Multilingual" in v.get("VoiceTag", {}).get("ContentCategories", []),
                }
                for v in voices
            ]
            logger.info(f"VOICE_SERVICE loaded voices={len(_voices_cache)}")
        except Exception as e:
            logger.error(f"VOICE_SERVICE_ERROR failed to load voices: {e}")
            _voices_cache = []

    return _voices_cache


def get_voice_list_sync() -> list[dict]:
    """Synchronous wrapper for initial voice loading"""
    return asyncio.run(get_all_voices()) if _voices_cache is None else _voices_cache
