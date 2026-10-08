"""`PollyAudioService` - specifically the sentence-boundary chunking and
ffmpeg-concat logic added so a long narration script (now that videos can
run up to 10 minutes) is never silently truncated by Polly's real ~3000
character per-request limit. Mocks boto3 and subprocess so these stay fast
and never touch AWS or need a working ffmpeg.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.audio.polly import PollyAudioService, _split_into_chunks


def test_split_into_chunks_short_text_is_a_single_chunk():
    text = "This is a short narration script. It fits in one request easily."
    assert _split_into_chunks(text, max_chars=2900) == [text]


def test_split_into_chunks_never_splits_mid_sentence():
    sentence = "This is one sentence of a certain length that repeats. "
    text = sentence * 80  # long enough to force multiple chunks well under 2900 chars/sentence
    chunks = _split_into_chunks(text, max_chars=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200
        # Every chunk should end where a sentence ends, not mid-word.
        assert chunk.rstrip().endswith(".")


def test_split_into_chunks_hard_slices_an_oversized_single_sentence():
    huge_sentence = "word " * 700  # no '.', one giant "sentence" over the limit
    chunks = _split_into_chunks(huge_sentence, max_chars=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    assert "".join(chunks) == huge_sentence


def test_synthesize_short_script_makes_one_polly_call_no_concat(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.aws_access_key_id", "AKIA...")
    monkeypatch.setattr("app.core.config.settings.aws_secret_access_key", "secret")

    mock_client = MagicMock()
    mock_client.synthesize_speech.return_value = {"AudioStream": MagicMock(read=lambda: b"fake-mp3-bytes")}

    with patch("boto3.client", return_value=mock_client) as mock_boto_client, patch(
        "app.services.audio.polly._concat_mp3s"
    ) as mock_concat:
        result = PollyAudioService().synthesize("A short narration script.")

    assert mock_boto_client.call_count == 1
    assert mock_client.synthesize_speech.call_count == 1
    mock_concat.assert_not_called()
    assert result is not None
    assert result.read_bytes() == b"fake-mp3-bytes"
    result.unlink(missing_ok=True)


def test_synthesize_long_script_makes_multiple_calls_and_concatenates(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.aws_access_key_id", "AKIA...")
    monkeypatch.setattr("app.core.config.settings.aws_secret_access_key", "secret")
    monkeypatch.setattr("app.services.audio.polly._MAX_CHUNK_CHARS", 50)

    long_script = "This is sentence number one. " * 20  # forces several chunks at max_chars=50

    mock_client = MagicMock()
    mock_client.synthesize_speech.return_value = {"AudioStream": MagicMock(read=lambda: b"chunk-bytes")}

    concatenated = Path(__file__).parent / "_fixture_concat_output.mp3"
    concatenated.write_bytes(b"joined-mp3-bytes")

    with patch("boto3.client", return_value=mock_client), patch(
        "app.services.audio.polly._concat_mp3s", return_value=concatenated
    ) as mock_concat:
        result = PollyAudioService().synthesize(long_script)

    assert mock_client.synthesize_speech.call_count > 1
    mock_concat.assert_called_once()
    assert result == concatenated
    concatenated.unlink(missing_ok=True)


def test_synthesize_returns_none_on_empty_script():
    assert PollyAudioService().synthesize("") is None
    assert PollyAudioService().synthesize("   ") is None


def test_synthesize_returns_none_when_polly_raises(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.aws_access_key_id", "AKIA...")
    monkeypatch.setattr("app.core.config.settings.aws_secret_access_key", "secret")

    with patch("boto3.client", side_effect=RuntimeError("no credentials")):
        assert PollyAudioService().synthesize("Some narration.") is None
