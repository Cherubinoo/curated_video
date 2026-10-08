from app.core.config import settings
from app.services.audio.base import AudioService  # noqa: F401
from app.services.audio.noop import NoOpAudioService  # noqa: F401

# Per product decision: Amazon Polly only. ElevenLabsAudioService still
# exists (app/services/audio/elevenlabs.py) as a working, ready-to-swap-in
# implementation of the same AudioService interface, but it is intentionally
# not in the active selection path below.


def get_voice_provider_name() -> str:
    """The provider `get_audio_service()` will actually select, as one of
    the VideoSpecification DSL's `audio.voice_provider` values. Used by
    specification generators so the spec's metadata matches reality instead
    of guessing independently - see bedrock_specification_generator.py."""
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        return "polly"
    return "none"


def get_audio_service() -> AudioService:
    if get_voice_provider_name() == "polly":
        from app.services.audio.polly import PollyAudioService

        return PollyAudioService()
    return NoOpAudioService()


__all__ = ["AudioService", "NoOpAudioService", "get_audio_service", "get_voice_provider_name"]
