"""
eidosSpeech v2 — Round-Robin Proxy Manager
Optional proxy support — empty EIDOS_PROXIES = direct connection.

Fallback chain:
  1. Round-robin through healthy proxies
  2. If a proxy fails MAX_FAILURES times → disabled for COOLDOWN_SECONDS (10 min)
  3. If ALL proxies disabled → return None (direct connection via VPS IP)
  4. After cooldown expires → proxy is re-tried automatically

This means: proxy mati sementara = otomatis coba lagi nanti.
            proxy semua mati = langsung pake direct connection, tetap jalan.
"""

import asyncio
import itertools
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 600  # 10 minutes before retrying a failed proxy


class ProxyManager:
    """
    Round-robin proxy manager with failure tracking and auto-recovery.

    - Empty proxy list → always return None (direct connection)
    - Proxy fails MAX_FAILURES times consecutively → disabled for 10 minutes
    - All proxies disabled → return None (direct connection via VPS IP)
    - After cooldown → proxy is automatically re-enabled
    """

    MAX_FAILURES = 3

    def __init__(self, proxy_list: list[str]):
        self._proxies = proxy_list
        self._cycle = itertools.cycle(proxy_list) if proxy_list else None
        self._failures: dict[str, int] = defaultdict(int)
        self._disabled_until: dict[str, float] = {}  # proxy → unix timestamp
        self._lock = asyncio.Lock()

        if proxy_list:
            logger.info(f"PROXY_MANAGER initialized proxies={len(proxy_list)} — direct fallback always active")
        else:
            logger.info("PROXY_MANAGER no proxies configured — direct connection mode")

    def _is_healthy(self, proxy: str) -> bool:
        """Proxy is healthy if: failure count < MAX or cooldown has expired"""
        disabled_until = self._disabled_until.get(proxy, 0)
        if time.monotonic() >= disabled_until:
            # Cooldown expired — reset and re-enable
            if disabled_until > 0:
                logger.info(f"PROXY_RECOVERED proxy={proxy} — re-enabling after cooldown")
                self._failures[proxy] = 0
                self._disabled_until[proxy] = 0
            return True
        return False

    async def get_next(self) -> str | None:
        """
        Return next healthy proxy URL, or None for direct connection.

        Returns None when:
        - No proxies configured (empty EIDOS_PROXIES)
        - All proxies are in cooldown (all failed recently)
        → In both cases, TTS will proceed via direct connection (VPS IP)
        """
        if not self._proxies or not self._cycle:
            return None

        async with self._lock:
            tried = 0
            total = len(self._proxies)
            while tried < total:
                proxy = next(self._cycle)
                if self._is_healthy(proxy):
                    return proxy
                tried += 1

        # All proxies are in cooldown — use direct connection
        logger.warning("PROXY_ALL_FAILED falling_back_to_direct — TTS continues via VPS IP")
        return None

    async def mark_success(self, proxy: str):
        """Reset failure count on successful use"""
        async with self._lock:
            self._failures[proxy] = 0
            self._disabled_until[proxy] = 0

    async def mark_failure(self, proxy: str):
        """Increment failure count — disable proxy for COOLDOWN_SECONDS at MAX_FAILURES"""
        async with self._lock:
            self._failures[proxy] += 1
            failures = self._failures[proxy]
            if failures >= self.MAX_FAILURES:
                self._disabled_until[proxy] = time.monotonic() + COOLDOWN_SECONDS
                logger.warning(
                    f"PROXY_DISABLED proxy={proxy} failures={failures} — "
                    f"cooldown {COOLDOWN_SECONDS}s, using direct fallback"
                )

    def reset_all(self):
        """Reset all failure counts and cooldowns (called by periodic cleanup)"""
        self._failures.clear()
        self._disabled_until.clear()
        logger.info("PROXY_RESET all proxy failure counts cleared")

    def get_status(self) -> dict:
        """Return proxy status for health endpoint"""
        if not self._proxies:
            return {"enabled": False, "mode": "direct", "count": 0, "healthy": 0, "failed": 0}

        now = time.monotonic()
        healthy = sum(1 for p in self._proxies if now >= self._disabled_until.get(p, 0))
        failed = len(self._proxies) - healthy
        return {
            "enabled": True,
            "mode": "proxy+direct_fallback",
            "count": len(self._proxies),
            "healthy": healthy,
            "failed": failed,
        }


# Singleton — initialized from settings in main.py
_proxy_manager: ProxyManager = None


def get_proxy_manager() -> ProxyManager:
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager([])
    return _proxy_manager


def init_proxy_manager(proxy_list: list[str]) -> ProxyManager:
    global _proxy_manager
    _proxy_manager = ProxyManager(proxy_list)
    return _proxy_manager
