"""
eidosSpeech v2 — API v1 Router Registration
Registers: auth, admin, tts, voices, health, batch (410)
"""

from fastapi import APIRouter

from app.api.v1 import auth, admin, tts, voices, health, batch

router = APIRouter()

# Auth endpoints: /api/v1/auth/*
router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Admin endpoints: /api/v1/admin/*
router.include_router(admin.router, prefix="/admin", tags=["admin"])

# TTS: /api/v1/tts
router.include_router(tts.router, tags=["tts"])

# Voices: /api/v1/voices
router.include_router(voices.router, tags=["voices"])

# Health: /api/v1/health
router.include_router(health.router, tags=["health"])

# Batch: /api/v1/batch/tts → 410 Gone
router.include_router(batch.router, prefix="/batch", tags=["batch"])
