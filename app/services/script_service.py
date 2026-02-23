"""
eidosSpeech v2.1 — Multi-Voice Script Service
Parse and generate multi-voice dialog/podcast audio.
"""

import io
import re
import logging
from typing import List
from dataclasses import dataclass

from pydub import AudioSegment

from app.services.tts_engine import get_tts_engine

logger = logging.getLogger(__name__)


@dataclass
class ScriptLine:
    """Single line in a multi-voice script"""
    speaker: str
    text: str
    line_number: int


def parse_script(raw_script: str) -> List[ScriptLine]:
    """
    Parse multi-voice script format: [Speaker] text
    Lines without [Speaker] tag inherit previous speaker.
    
    Example:
        [Gadis] Hello, welcome to our podcast
        [Ardi] Thank you for having me
        This line also belongs to Ardi
        [Gadis] Let's start with the first topic
    
    Returns list of ScriptLine objects.
    """
    lines = []
    current_speaker = None
    line_number = 0
    
    for raw_line in raw_script.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        
        line_number += 1
        
        # Check for [Speaker] tag
        match = re.match(r'^\[([^\]]+)\]\s*(.+)$', line)
        if match:
            current_speaker = match.group(1).strip()
            text = match.group(2).strip()
        else:
            # No tag, use previous speaker
            text = line
        
        if not current_speaker:
            raise ValueError(
                f"Line {line_number}: No speaker defined. "
                "First line must have [Speaker] tag."
            )
        
        if not text:
            continue
        
        lines.append(ScriptLine(
            speaker=current_speaker,
            text=text,
            line_number=line_number
        ))
    
    if not lines:
        raise ValueError("Script is empty or contains no valid lines")
    
    return lines


async def generate_script_audio(
    lines: List[ScriptLine],
    voice_map: dict[str, str],
    pause_ms: int = 500,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
) -> bytes:
    """
    Generate multi-voice audio from parsed script lines.
    
    Args:
        lines: List of ScriptLine objects
        voice_map: Dict mapping speaker names to voice IDs
                   e.g. {"Gadis": "id-ID-GadisNeural", "Ardi": "id-ID-ArdiNeural"}
        pause_ms: Milliseconds of silence between lines (0-3000)
        rate: Speech rate for all voices
        pitch: Pitch for all voices
        volume: Volume for all voices
    
    Returns:
        MP3 audio bytes
    """
    tts_engine = get_tts_engine()
    segments = []
    
    logger.info(f"SCRIPT_GENERATE lines={len(lines)} pause={pause_ms}ms")
    
    for i, line in enumerate(lines, 1):
        # Get voice for this speaker
        voice = voice_map.get(line.speaker)
        if not voice:
            # Fallback: use speaker name as voice ID if not in map
            voice = line.speaker
            logger.warning(
                f"SCRIPT_LINE {i}: Speaker '{line.speaker}' not in voice_map, "
                f"using as voice ID directly"
            )
        
        # Generate TTS for this line
        try:
            audio_bytes = await tts_engine.synthesize(
                text=line.text,
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
            )
            
            # Convert to AudioSegment
            segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
            segments.append(segment)
            
            logger.info(
                f"SCRIPT_LINE {i}/{len(lines)}: "
                f"speaker={line.speaker} voice={voice} "
                f"chars={len(line.text)} duration={len(segment)}ms"
            )
            
        except Exception as e:
            logger.error(
                f"SCRIPT_LINE {i} FAILED: speaker={line.speaker} "
                f"voice={voice} error={e}"
            )
            raise RuntimeError(
                f"Failed to generate audio for line {i} "
                f"(speaker: {line.speaker}): {e}"
            )
    
    # Merge segments with pauses
    if not segments:
        raise RuntimeError("No audio segments generated")
    
    merged = segments[0]
    silence = AudioSegment.silent(duration=pause_ms)
    
    for segment in segments[1:]:
        merged += silence + segment
    
    # Export to MP3
    output = io.BytesIO()
    merged.export(output, format="mp3", bitrate="48k")
    audio_bytes = output.getvalue()
    
    logger.info(
        f"SCRIPT_COMPLETE lines={len(lines)} "
        f"duration={len(merged)}ms size={len(audio_bytes)} bytes"
    )
    
    return audio_bytes
