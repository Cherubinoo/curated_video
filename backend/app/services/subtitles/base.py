"""SubtitleService interface. Later implementations: Whisper-generated
subtitles, user-uploaded SRT/VTT, burned-in subtitles via FFmpeg."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SubtitleService(ABC):
    @abstractmethod
    def generate(self, script: str, audio_path: Path | None) -> Path | None:
        """Returns a local path to a generated .srt/.vtt file, or None if
        subtitles are disabled."""
