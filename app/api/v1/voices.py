"""
eidosSpeech v2 — Voices Endpoint
GET /api/v1/voices — List all available TTS voices.
Public endpoint — no auth required.
"""

import json
from pathlib import Path
from fastapi import APIRouter, Query

from app.services.voice_service import get_all_voices

router = APIRouter()


def load_presets():
    """Load voice presets from JSON file."""
    presets_path = Path(__file__).parent.parent.parent / "data" / "presets.json"
    with open(presets_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_voice_styles():
    """Load voice styles configuration from JSON file."""
    styles_path = Path(__file__).parent.parent.parent / "data" / "voice_styles.json"
    with open(styles_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/voices")
async def list_voices(
    language: str = Query(None, description="Filter by language code, e.g. 'id-ID', 'en-US'"),
    gender: str = Query(None, description="Filter by gender: 'Male' or 'Female'"),
    search: str = Query(None, description="Search by voice name or language"),
):
    """
    List all available TTS voices (1,200+ voices).
    Optionally filter by language code, gender, or search term.
    """
    voices = await get_all_voices()

    # Apply filters
    if language:
        voices = [v for v in voices if v["language_code"].lower().startswith(language.lower())]

    if gender:
        voices = [v for v in voices if v["gender"].lower() == gender.lower()]

    if search:
        search_lower = search.lower()
        voices = [v for v in voices if
                  search_lower in v["name"].lower() or
                  search_lower in v["language"].lower() or
                  search_lower in v["language_code"].lower()]

    return {
        "voices": voices,
        "total": len(voices),
        "filters": {
            "language": language,
            "gender": gender,
            "search": search,
        }
    }


@router.get("/voices/presets")
async def get_presets():
    """
    Get voice character presets with pre-configured settings.
    Returns presets grouped by category (professional, creative, regional).
    """
    return load_presets()


@router.get("/voices/styles")
async def get_voice_styles():
    """
    Get supported emotion/style tags per voice.
    Returns mapping of voice IDs to available styles and descriptions.
    """
    return load_voice_styles()
