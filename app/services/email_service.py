"""
eidosSpeech v2 — Multi-Provider Email Service
Fallback chain: Brevo SMTP → Mailtrap SMTP → Resend API

Features (adapted from eidosStack EmailDispatcher pattern):
  - Provider circuit breaker: jika provider sudah gagal N kali berturut-turut,
    skip langsung ke provider berikutnya tanpa mencoba lagi sampai cooldown habis.
  - Daily limit detection: deteksi error 550/421/429 dari SMTP / HTTP 429 dari Resend
    → langsung mark provider sebagai "limited", bypass untuk sisa hari ini.
  - Non-blocking: registration flow tidak terblokir jika semua provider gagal.
  - critical=True: password reset — raise exception jika semua provider gagal.
"""

import logging
import time
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import httpx

from app.config import settings
from app.core.exceptions import EmailDeliveryError

logger = logging.getLogger(__name__)


# ── Failure Classification ────────────────────────────────────────────────────

def _is_limit_error_smtp(error: Exception) -> bool:
    """
    Detect daily/monthly sending limit from SMTP error codes.
    Brevo returns 550 or 421 when daily free limit (300/day) is exhausted.
    """
    msg = str(error).lower()
    return any(x in msg for x in [
        "550",       # 5.7.0 daily limit reached (Brevo)
        "421",       # 4.2.1 temp limit
        "daily",
        "limit",
        "quota",
        "exceeded",
        "too many",
    ])


def _is_limit_error_http(status_code: int) -> bool:
    """Detect HTTP rate limit from API providers (Resend)."""
    return status_code in (429, 550, 503)


# ── Provider Base ─────────────────────────────────────────────────────────────

class ProviderStatus:
    """
    Per-provider health state.
    - failure_count: consecutive failures
    - cooldown_until: unix timestamp, skip provider until this time
    """
    def __init__(self):
        self.failure_count: int = 0
        self.cooldown_until: float = 0.0  # 0 = not in cooldown
        self.last_error: str = ""

    @property
    def is_available(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def mark_success(self):
        self.failure_count = 0
        self.cooldown_until = 0.0
        self.last_error = ""

    def mark_failure(self, error: str, is_limit: bool = False):
        self.failure_count += 1
        self.last_error = error
        if is_limit:
            # Daily limit: cooldown until next day (12 hours)
            self.cooldown_until = time.monotonic() + (12 * 3600)
            logger.warning(f"EMAIL_PROVIDER_LIMITED name={error[:60]} — cooldown 12h")
        elif self.failure_count >= 3:
            # 3 consecutive failures → short circuit break (15 min)
            self.cooldown_until = time.monotonic() + 900
            logger.warning(f"EMAIL_PROVIDER_CIRCUIT_BREAK failures={self.failure_count} — cooldown 15m")


class EmailProvider(ABC):
    name: str = "base"
    status: ProviderStatus

    def __init__(self):
        self.status = ProviderStatus()

    @abstractmethod
    async def _do_send(self, to: str, subject: str, html: str) -> None:
        """Provider-specific send logic. Raises on failure."""
        ...

    async def send(self, to: str, subject: str, html: str) -> None:
        """
        Wraps _do_send with circuit breaker + failure classification.
        Raises the original exception on failure.
        """
        if not self.status.is_available:
            remaining = int(self.status.cooldown_until - time.monotonic())
            raise EmailDeliveryError(
                f"Provider {self.name} is in cooldown for {remaining}s "
                f"(last error: {self.status.last_error[:80]})"
            )

        try:
            await self._do_send(to, subject, html)
            self.status.mark_success()
        except Exception as e:
            is_limit = self._classify_limit(e)
            self.status.mark_failure(str(e), is_limit=is_limit)
            raise

    def _classify_limit(self, error: Exception) -> bool:
        return False  # Override in child classes


# ── SMTP Provider ─────────────────────────────────────────────────────────────

class SmtpProvider(EmailProvider):
    """
    Generic SMTP provider — works with Brevo, Mailtrap, any SMTP relay.
    Brevo free: 300 emails/day. Detects limit via 550/421 SMTP codes.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        name: str = "SMTP",
    ):
        super().__init__()
        self.name = name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr

    def _classify_limit(self, error: Exception) -> bool:
        return _is_limit_error_smtp(error)

    async def _do_send(self, to: str, subject: str, html: str) -> None:
        message = MIMEMultipart("alternative")
        message["From"] = self.from_addr
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(html, "html"))

        use_tls = self.port == 465
        use_starttls = self.port == 587

        await aiosmtplib.send(
            message,
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            use_tls=use_tls,
            start_tls=use_starttls,
            timeout=20,
        )


# ── Resend API Provider ───────────────────────────────────────────────────────

class ResendProvider(EmailProvider):
    """
    Resend REST API — HTTP-based fallback, no SMTP needed.
    Free plan: 100 emails/day. Detects limit via HTTP 429.
    """
    name = "Resend"

    def __init__(self, api_key: str, from_addr: str):
        super().__init__()
        self.api_key = api_key
        self.from_addr = from_addr

    def _classify_limit(self, error: Exception) -> bool:
        # Check if stored as attribute from _do_send
        if hasattr(error, "_is_rate_limit"):
            return error._is_rate_limit
        return "429" in str(error) or "rate_limit" in str(error).lower()

    async def _do_send(self, to: str, subject: str, html: str) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": self.from_addr,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
            if not response.is_success:
                err = Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                err._is_rate_limit = _is_limit_error_http(response.status_code)
                raise err


# ── Email Dispatcher ──────────────────────────────────────────────────────────

class EmailDispatcher:
    """
    Multi-provider email dispatcher with circuit breaker fallback chain.

    Chain: Brevo SMTP → Mailtrap SMTP → Resend API

    Flow:
      1. Try Brevo SMTP   — skip if in cooldown (daily limit / 3+ failures)
      2. Try Mailtrap SMTP — skip if in cooldown
      3. Try Resend API   — skip if in cooldown
      4. If all fail → log error, return False (non-blocking)
                     → raise EmailDeliveryError if critical=True

    Circuit breaker states:
      - OK: send normally
      - LIMITED (daily limit hit): skip for 12 hours
      - BROKEN (3+ consecutive failures): skip for 15 minutes
      - Automatically recovered after cooldown expires
    """

    def __init__(self):
        self.providers: list[EmailProvider] = []
        self._build_chain()

    def _build_chain(self):
        """Build provider chain: Brevo SMTP → Mailtrap SMTP → Resend API"""
        if settings.smtp_host:
            self.providers.append(SmtpProvider(
                host=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                from_addr=settings.smtp_from,
                name="Brevo-SMTP",
            ))

        if settings.smtp_fallback_host:
            self.providers.append(SmtpProvider(
                host=settings.smtp_fallback_host,
                port=settings.smtp_fallback_port,
                username=settings.smtp_fallback_username,
                password=settings.smtp_fallback_password,
                from_addr=settings.smtp_from,
                name="Mailtrap-SMTP",
            ))

        if settings.resend_api_key:
            self.providers.append(ResendProvider(
                api_key=settings.resend_api_key,
                from_addr=settings.smtp_from,
            ))

        names = [p.name for p in self.providers]
        logger.info(f"EMAIL_CHAIN configured providers={names}")

        if not self.providers:
            logger.warning("EMAIL_CHAIN no email providers configured!")

    def get_status(self) -> list[dict]:
        """Return current health status of all providers (for admin/monitoring)."""
        now = time.monotonic()
        result = []
        for p in self.providers:
            cooldown_remaining = max(0, int(p.status.cooldown_until - now))
            result.append({
                "name": p.name,
                "available": p.status.is_available,
                "failure_count": p.status.failure_count,
                "cooldown_remaining_s": cooldown_remaining,
                "last_error": p.status.last_error[:100] if p.status.last_error else None,
            })
        return result

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        critical: bool = False,
    ) -> bool:
        """
        Send email via provider chain with automatic fallback.

        Args:
            to: Recipient email address
            subject: Email subject
            html: HTML email body
            critical: If True, raises EmailDeliveryError when all providers fail.
                      Use for password reset. For registration, keep False (non-blocking).

        Returns:
            True if sent successfully, False if all providers failed (non-critical only).
        """
        last_error = None
        attempted = []

        for provider in self.providers:
            if not provider.status.is_available:
                remaining = int(provider.status.cooldown_until - time.monotonic())
                logger.debug(
                    f"EMAIL_SKIP provider={provider.name} "
                    f"cooldown={remaining}s reason={provider.status.last_error[:60]}"
                )
                continue

            attempted.append(provider.name)
            try:
                await provider.send(to, subject, html)
                logger.info(f"EMAIL_SENT provider={provider.name} to={to}")
                return True
            except Exception as e:
                last_error = e
                logger.warning(
                    f"EMAIL_FAIL provider={provider.name} to={to} "
                    f"failures={provider.status.failure_count} "
                    f"cooldown={'yes' if not provider.status.is_available else 'no'} "
                    f"error={str(e)[:120]}"
                )
                continue  # Try next provider

        # All providers failed or skipped
        skipped = [p.name for p in self.providers if p.name not in attempted]
        logger.error(
            f"ALL_EMAIL_PROVIDERS_FAILED to={to} "
            f"attempted={attempted} skipped={skipped}"
        )

        if critical:
            raise EmailDeliveryError(
                f"Unable to send email to {to}. "
                f"All providers failed or are in cooldown. "
                f"Please try again later."
            )

        return False  # Non-blocking — registration continues


# ── Email Templates ───────────────────────────────────────────────────────────

def _brand_header() -> str:
    return """
    <div style="background:#064e3b; padding:20px 40px; text-align:center;">
        <h1 style="color:#10B981; margin:0; font-size:24px; font-weight:700; letter-spacing:-0.5px;">
            eidosSpeech
        </h1>
        <p style="color:#6ee7b7; margin:4px 0 0; font-size:13px;">Free Text-to-Speech API</p>
    </div>
    """


def _brand_footer() -> str:
    return """
    <div style="background:#111; padding:20px 40px; text-align:center; border-top:1px solid #333;">
        <p style="color:#555; font-size:12px; margin:0;">
            Part of the <a href="https://eidosstack.com" style="color:#10B981;">eidosStack</a> ecosystem.
        </p>
        <p style="color:#444; font-size:11px; margin:8px 0 0;">
            You're receiving this because you registered at eidosSpeech.
        </p>
    </div>
    """


def verification_email(token: str, domain: str) -> tuple[str, str]:
    """Email verification template"""
    subject = "Verify your eidosSpeech account"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:0; background:#0a0a0a; font-family:Inter,system-ui,sans-serif;">
        <div style="max-width:600px; margin:0 auto;">
            {_brand_header()}
            <div style="background:#111; padding:40px;">
                <h2 style="color:#f5f5f5; margin:0 0 16px; font-size:20px;">Verify your email address</h2>
                <p style="color:#aaa; font-size:15px; line-height:1.6; margin:0 0 32px;">
                    You're almost there! Click the button below to verify your email and get your free API key.
                </p>
                <div style="text-align:center; margin:32px 0;">
                    <a href="https://{domain}/verify-email?token={token}"
                       style="display:inline-block; background:#10B981; color:#fff; padding:14px 32px;
                              border-radius:8px; text-decoration:none; font-weight:600; font-size:16px;">
                        ✓ Verify Email Address
                    </a>
                </div>
                <p style="color:#555; font-size:13px; line-height:1.5;">
                    This link expires in <strong style="color:#888;">24 hours</strong>.<br>
                    If you didn't create an eidosSpeech account, you can safely ignore this email.
                </p>
            </div>
            {_brand_footer()}
        </div>
    </body>
    </html>
    """
    return subject, html


def reset_password_email(token: str, domain: str, ip: str) -> tuple[str, str]:
    """Password reset template"""
    subject = "Reset your eidosSpeech password"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:0; background:#0a0a0a; font-family:Inter,system-ui,sans-serif;">
        <div style="max-width:600px; margin:0 auto;">
            {_brand_header()}
            <div style="background:#111; padding:40px;">
                <h2 style="color:#f5f5f5; margin:0 0 16px; font-size:20px;">Reset your password</h2>
                <p style="color:#aaa; font-size:15px; line-height:1.6; margin:0 0 32px;">
                    We received a request to reset your password. Click below to create a new one.
                </p>
                <div style="text-align:center; margin:32px 0;">
                    <a href="https://{domain}/reset-password?token={token}"
                       style="display:inline-block; background:#10B981; color:#fff; padding:14px 32px;
                              border-radius:8px; text-decoration:none; font-weight:600; font-size:16px;">
                        Reset Password
                    </a>
                </div>
                <div style="background:#1a1a1a; border:1px solid #333; border-radius:8px; padding:16px; margin:24px 0;">
                    <p style="color:#888; font-size:13px; margin:0;">
                        ⚠️ This link expires in <strong style="color:#f59e0b;">1 hour</strong>.
                    </p>
                    <p style="color:#666; font-size:12px; margin:8px 0 0;">
                        Requested from IP: <code style="color:#10B981;">{ip}</code>
                    </p>
                </div>
                <p style="color:#555; font-size:13px;">
                    If you didn't request a password reset, your account is safe — ignore this email.
                </p>
            </div>
            {_brand_footer()}
        </div>
    </body>
    </html>
    """
    return subject, html


def welcome_email(api_key: str, domain: str) -> tuple[str, str]:
    """Welcome email with API key and quick start"""
    subject = "Welcome to eidosSpeech! Here's your API key 🎉"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:0; background:#0a0a0a; font-family:Inter,system-ui,sans-serif;">
        <div style="max-width:600px; margin:0 auto;">
            {_brand_header()}
            <div style="background:#111; padding:40px;">
                <h2 style="color:#f5f5f5; margin:0 0 8px; font-size:20px;">Welcome to eidosSpeech! 🎉</h2>
                <p style="color:#aaa; font-size:15px; margin:0 0 32px;">Your account is verified. Here's your API key:</p>

                <div style="background:#0d2b1a; border:1px solid #10B981; border-radius:8px; padding:16px; margin:24px 0; text-align:center;">
                    <p style="color:#6ee7b7; font-size:12px; margin:0 0 8px; text-transform:uppercase; letter-spacing:1px;">Your API Key</p>
                    <code style="color:#10B981; font-size:18px; font-weight:600; letter-spacing:1px;">{api_key}</code>
                </div>

                <p style="color:#aaa; font-size:14px; margin:24px 0 12px;"><strong style="color:#f5f5f5;">Quick Start:</strong></p>
                <pre style="background:#1a1a1a; border:1px solid #333; border-radius:8px; padding:16px; overflow-x:auto;
                            color:#10B981; font-size:13px; line-height:1.5; margin:0 0 24px;">curl -X POST https://{domain}/api/v1/tts \\
  -H "X-API-Key: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"text":"Halo, selamat datang!","voice":"id-ID-GadisNeural"}}' \\
  --output audio.mp3</pre>

                <div style="text-align:center;">
                    <a href="https://{domain}/dashboard"
                       style="display:inline-block; background:#10B981; color:#fff; padding:12px 24px;
                              border-radius:8px; text-decoration:none; font-weight:600; font-size:15px; margin:0 8px;">
                        Go to Dashboard
                    </a>
                    <a href="https://{domain}/api-docs"
                       style="display:inline-block; background:#1a1a1a; color:#10B981; padding:12px 24px;
                              border-radius:8px; text-decoration:none; font-weight:600; font-size:15px;
                              border:1px solid #10B981; margin:0 8px;">
                        API Docs
                    </a>
                </div>

                <div style="border-top:1px solid #222; margin:32px 0; padding-top:24px;">
                    <p style="color:#666; font-size:13px; margin:0;">
                        <strong style="color:#888;">Free tier limits:</strong><br>
                        30 requests/day · 1,000 characters/request · 3 requests/minute
                    </p>
                </div>
            </div>
            {_brand_footer()}
        </div>
    </body>
    </html>
    """
    return subject, html


# ── Singleton ─────────────────────────────────────────────────────────────────
_dispatcher: EmailDispatcher = None


def get_email_dispatcher() -> EmailDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = EmailDispatcher()
    return _dispatcher
