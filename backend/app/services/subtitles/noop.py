from __future__ import annotations

from pathlib import Path

from app.services.subtitles.base import SubtitleService


class NoOpSubtitleService(SubtitleService):
    """Default implementation: subtitles are optional and off by default,
    per product spec Section 14."""

    def generate(self, script: str, audio_path: Path | None) -> Path | None:
        return None
