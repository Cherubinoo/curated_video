from __future__ import annotations

from pathlib import Path

from app.services.audio.base import AudioService


class NoOpAudioService(AudioService):
    """Default implementation: no TTS provider configured, so every video
    renders animation-only, per product spec Section 13 ("audio =
    optional")."""

    def synthesize(self, script: str) -> Path | None:
        return None
