"""
eidosSpeech v2 — Batch TTS Endpoint
POST /api/v1/batch/tts → 410 Gone
Batch TTS was a v1 feature. v2 is single-request only.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/tts")
@router.get("/tts")
async def batch_gone():
    """Batch TTS is not available in v2. Single-request only."""
    return JSONResponse(
        status_code=410,
        content={
            "error": "Gone",
            "message": "Batch TTS is not available in eidosSpeech v2.",
            "detail": {
                "reason": "v2 is single-request only.",
                "docs": "https://eidosspeech.xyz/api-docs",
            }
        }
    )
