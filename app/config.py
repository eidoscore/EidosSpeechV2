"""
eidosSpeech v2 — Configuration
Extends v1 settings with auth, database, email, rate limiting, proxy, admin settings.
"""

import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EIDOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Server ───────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = False
    public_domain: str = "eidosspeech.xyz"

    # ── Database ──────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/db/eidosspeech.db"

    # ── JWT / Auth ────────────────────────────────────────────
    secret_key: str = "change-me-in-production-min-64-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # ── Email — Primary SMTP ──────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "eidosSpeech <noreply@eidosspeech.xyz>"

    # ── Email — Fallback SMTP ─────────────────────────────────
    smtp_fallback_host: str = ""
    smtp_fallback_port: int = 587
    smtp_fallback_username: str = ""
    smtp_fallback_password: str = ""

    # ── Email — Resend API fallback ───────────────────────────
    resend_api_key: str = ""

    # ── Cloudflare Turnstile (optional) ──────────────────────
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    turnstile_enabled: bool = False
    turnstile_allow_bypass: bool = False

    # ── Rate Limits — Anonymous (Web UI only) ────────────────
    anon_char_limit: int = 500
    anon_req_per_day: int = 5
    anon_req_per_min: int = 1

    # ── Rate Limits — Registered (Free) ──────────────────────
    free_char_limit: int = 1000
    free_req_per_day: int = 30
    free_req_per_min: int = 3

    # ── Proxy (comma-separated, optional) ────────────────────
    proxies: str = ""  # empty = no proxy, "http://p1,http://p2" = round-robin

    # ── TTS (from v1) ─────────────────────────────────────────
    default_voice: str = "id-ID-GadisNeural"
    max_concurrent: int = 3

    # ── Cache (from v1) ───────────────────────────────────────
    cache_dir: str = "./data/cache"
    cache_max_size_gb: float = 5.0
    cache_ttl_days: int = 30

    # ── Google AdSense ────────────────────────────────────────
    adsense_client_id: str = ""
    adsense_slot_top: str = ""
    adsense_slot_below: str = ""

    # ── Admin ─────────────────────────────────────────────────
    admin_key: str = "change-me-admin-key"

    # ── Helpers ───────────────────────────────────────────────

    @property
    def proxy_list(self) -> list[str]:
        """Parse comma-separated proxies into list"""
        if not self.proxies:
            return []
        return [p.strip() for p in self.proxies.split(",") if p.strip()]

    def validate_startup(self):
        """
        Called on app startup — fail loudly if critical config missing.
        Validates: SECRET_KEY, ADMIN_KEY not default, at least 1 email provider.
        """
        errors = []

        if self.secret_key == "change-me-in-production-min-64-bytes":
            errors.append("EIDOS_SECRET_KEY must be changed from default value")

        if self.admin_key == "change-me-admin-key":
            errors.append("EIDOS_ADMIN_KEY must be changed from default value")

        if not self.smtp_host and not self.resend_api_key:
            errors.append(
                "At least one email provider required: "
                "set EIDOS_SMTP_HOST or EIDOS_RESEND_API_KEY"
            )

        if errors:
            for e in errors:
                logger.critical(f"CONFIG_ERROR: {e}")
            raise SystemExit(f"Startup validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        logger.info("CONFIG_VALID startup validation passed")


settings = Settings()
