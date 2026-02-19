"""
eidosSpeech v2 — Exception Classes
Consistent HTTP exception hierarchy for the API.
"""

from fastapi import HTTPException


class EidosSpeechError(HTTPException):
    """Base exception for eidosSpeech"""
    def __init__(self, status_code: int, error: str, message: str, detail: dict = None):
        self.error = error
        self.msg = message
        self.extra = detail or {}
        super().__init__(
            status_code=status_code,
            detail={"error": error, "message": message, "detail": self.extra}
        )


class ValidationError(EidosSpeechError):
    """400 — Invalid input (bad email, short password, empty text)"""
    def __init__(self, message: str, detail: dict = None):
        super().__init__(400, "ValidationError", message, detail)


class AuthenticationError(EidosSpeechError):
    """401 — Invalid/expired JWT, bad credentials"""
    def __init__(self, message: str = "Authentication required", detail: dict = None):
        super().__init__(401, "AuthenticationError", message, detail)


class ForbiddenError(EidosSpeechError):
    """403 — No API key + external origin, banned user, disabled key"""
    def __init__(self, message: str = "Access denied", detail: dict = None):
        super().__init__(403, "ForbiddenError", message, detail)


class NotFoundError(EidosSpeechError):
    """404 — Voice not found, user not found"""
    def __init__(self, message: str = "Not found", detail: dict = None):
        super().__init__(404, "NotFoundError", message, detail)


class ConflictError(EidosSpeechError):
    """409 — Email already registered"""
    def __init__(self, message: str = "Conflict", detail: dict = None):
        super().__init__(409, "ConflictError", message, detail)


class UnprocessableError(EidosSpeechError):
    """422 — Text too long for tier, invalid voice ID"""
    def __init__(self, message: str, detail: dict = None):
        super().__init__(422, "UnprocessableEntity", message, detail)


class RateLimitError(EidosSpeechError):
    """429 — Per-minute, per-day, or concurrent limit hit"""
    def __init__(self, message: str, retry_after: int = 60, detail: dict = None):
        self.retry_after = retry_after
        d = detail or {}
        d["retry_after"] = retry_after
        super().__init__(429, "RateLimitError", message, d)


class InternalError(EidosSpeechError):
    """500 — TTS engine failure, DB error (no internals exposed)"""
    def __init__(self, message: str = "Internal server error", detail: dict = None):
        super().__init__(500, "InternalError", message, detail)


class ServiceUnavailableError(EidosSpeechError):
    """503 — All proxies + direct failed"""
    def __init__(self, message: str = "Service temporarily unavailable", detail: dict = None):
        super().__init__(503, "ServiceUnavailable", message, detail)


class EmailDeliveryError(Exception):
    """Raised when all email providers fail (critical=True mode)"""
    pass
