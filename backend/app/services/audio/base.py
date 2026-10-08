"""AudioService interface. Later implementations: uploaded voice, ElevenLabs,
other TTS providers, user-recorded narration. Kept separate from core
rendering so TTS can be added without touching the animation engine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class AudioService(ABC):
    @abstractmethod
    def synthesize(self, script: str) -> Path | None:
        """Returns a local path to a synthesized/prepared audio file, or
        None if no audio should be attached (e.g. narration disabled)."""
