"""
eidosSpeech v2 — File-based Audio Cache
Cache TTS audio by content hash to avoid re-generating identical requests.
"""

import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class TTSCache:
    """File-based cache for TTS audio output. Keyed by content hash."""

    def __init__(self, cache_dir: str, max_size_gb: float, ttl_days: int):
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = int(max_size_gb * 1024 ** 3)
        self.ttl_seconds = ttl_days * 86400
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, text: str, voice: str, rate: str, pitch: str) -> str:
        """Generate SHA256 cache key from TTS parameters"""
        content = json.dumps({
            "text": text, "voice": voice, "rate": rate, "pitch": pitch
        }, ensure_ascii=False, sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()

    def get(self, cache_key: str) -> str | None:
        """Return cached file path if hit and not expired, else None"""
        path = self.cache_dir / f"{cache_key}.mp3"
        if not path.exists():
            return None

        # Check TTL
        age = time.time() - path.stat().st_mtime
        if age > self.ttl_seconds:
            path.unlink(missing_ok=True)
            return None

        # Touch to update access time (LRU-style)
        path.touch()
        return str(path)

    def put(self, cache_key: str, audio_bytes: bytes) -> str:
        """Save audio bytes to cache, return file path"""
        path = self.cache_dir / f"{cache_key}.mp3"
        path.write_bytes(audio_bytes)

        # Enforce max size (simple: remove oldest files)
        self._evict_if_needed()
        return str(path)

    def _evict_if_needed(self):
        """Remove oldest files if cache exceeds max size"""
        total = sum(f.stat().st_size for f in self.cache_dir.glob("*.mp3"))
        if total <= self.max_size_bytes:
            return

        files = sorted(
            self.cache_dir.glob("*.mp3"),
            key=lambda f: f.stat().st_mtime
        )

        for f in files:
            if total <= self.max_size_bytes * 0.8:  # evict to 80% of max
                break
            size = f.stat().st_size
            f.unlink(missing_ok=True)
            total -= size
            logger.debug(f"CACHE_EVICT file={f.name}")

    def stats(self) -> dict:
        """Return cache stats"""
        files = list(self.cache_dir.glob("*.mp3"))
        total_bytes = sum(f.stat().st_size for f in files)
        return {
            "files": len(files),
            "size_mb": round(total_bytes / 1024 ** 2, 2),
            "max_size_gb": settings.cache_max_size_gb,
        }


# Singleton
_cache: TTSCache = None


def get_cache() -> TTSCache:
    global _cache
    if _cache is None:
        _cache = TTSCache(
            settings.cache_dir,
            settings.cache_max_size_gb,
            settings.cache_ttl_days,
        )
    return _cache
