from app.services.subtitles.base import SubtitleService  # noqa: F401
from app.services.subtitles.noop import NoOpSubtitleService  # noqa: F401


def get_subtitle_service() -> SubtitleService:
    return NoOpSubtitleService()


__all__ = ["SubtitleService", "NoOpSubtitleService", "get_subtitle_service"]
