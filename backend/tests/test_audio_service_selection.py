"""`get_audio_service()`'s provider selection: Amazon Polly only, per
product decision (ElevenLabsAudioService still exists as a working,
ready-to-swap-in AudioService implementation, but is not in the active
selection path). Doesn't hit any real API - just verifies the right class
is chosen for a given settings combination, per the graceful-fallback
design every provider in this package follows.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.audio import get_audio_service, get_voice_provider_name
from app.services.audio.noop import NoOpAudioService


def test_defaults_to_noop_with_no_aws_credentials(monkeypatch):
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")

    assert isinstance(get_audio_service(), NoOpAudioService)
    assert get_voice_provider_name() == "none"


def test_selects_polly_when_aws_credentials_are_set(monkeypatch):
    from app.services.audio.polly import PollyAudioService

    monkeypatch.setattr(settings, "aws_access_key_id", "AKIAEXAMPLE")
    monkeypatch.setattr(settings, "aws_secret_access_key", "secret")

    assert isinstance(get_audio_service(), PollyAudioService)
    assert get_voice_provider_name() == "polly"


def test_requires_both_access_key_and_secret(monkeypatch):
    monkeypatch.setattr(settings, "aws_access_key_id", "AKIAEXAMPLE")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")

    assert isinstance(get_audio_service(), NoOpAudioService)


def test_polly_returns_none_on_blank_script():
    from app.services.audio.polly import PollyAudioService

    assert PollyAudioService().synthesize("") is None
    assert PollyAudioService().synthesize("   ") is None


def test_polly_synthesis_failure_returns_none_not_raises(monkeypatch):
    """A Polly/network failure must never break video creation - the caller
    (the worker) just proceeds animation-only."""
    from app.services.audio.polly import PollyAudioService

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated AWS failure")

    import boto3

    monkeypatch.setattr(boto3, "client", _boom)
    assert PollyAudioService().synthesize("Some narration text.") is None
