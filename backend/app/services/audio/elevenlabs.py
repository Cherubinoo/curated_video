"""AudioService backed by ElevenLabs text-to-speech.

Synthesis failures never fail the render - they log and return None, and
the worker proceeds to produce an animation-only video (audio has always
been optional per the product spec), the same way a NoOpAudioService would.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.audio.base import AudioService

logger = get_logger(__name__)

_TTS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_TIMEOUT_SECONDS = 60


class ElevenLabsAudioService(AudioService):
    def synthesize(self, script: str) -> Path | None:
        if not script or not script.strip():
            return None

        url = _TTS_URL_TEMPLATE.format(voice_id=settings.elevenlabs_voice_id)
        try:
            response = httpx.post(
                url,
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": script,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("elevenlabs_synthesis_failed", error=str(exc))
            return None

        fd, path_str = tempfile.mkstemp(suffix=".mp3", prefix="narration-")
        path = Path(path_str)
        with open(fd, "wb") as f:
            f.write(response.content)

        logger.info("elevenlabs_synthesis_succeeded", bytes=len(response.content))
        return path
