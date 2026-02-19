"""
eidosSpeech v2 — Voices Endpoint
GET /api/v1/voices — List all available TTS voices.
Public endpoint — no auth required.
"""

from fastapi import APIRouter, Query

from app.services.voice_service import get_all_voices

router = APIRouter()


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
