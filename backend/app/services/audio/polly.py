"""AudioService backed by Amazon Polly.

Needs real AWS IAM credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`,
boto3's standard SigV4 credential chain) - this is deliberately separate
from the Bedrock API key in `bedrock_specification_generator.py`, which is
a bearer token scoped to Bedrock/Bedrock Runtime only and cannot call Polly.

Same graceful-fallback contract as every other provider in this package:
any failure logs and returns None so the render continues animation-only
rather than failing the whole video - see `get_audio_service()`.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.audio.base import AudioService

logger = get_logger(__name__)

# Amazon Polly's synthesize_speech `Text` input (standard, non-SSML,
# real-time/non-async call) is hard-capped at 3000 characters per request -
# this is an AWS API limit, not a style choice. Longer scripts (expected
# now that videos can run up to 10 minutes - a 10-minute narration is
# easily 6000-9000+ characters) are split into multiple sentence-boundary
# chunks, synthesized as separate requests, and losslessly joined with
# ffmpeg's concat demuxer into one audio file - never silently truncated.
_MAX_CHUNK_CHARS = 2900

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Greedily packs whole sentences into chunks under `max_chars`, so a
    chunk boundary never lands mid-sentence (which would sound like an
    abrupt cut when the audio segments are joined). A single sentence
    longer than `max_chars` (rare) is hard-sliced as a last resort rather
    than sent to Polly oversized."""
    sentences = _SENTENCE_SPLIT_RE.split(text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(sentence) <= max_chars:
            current = sentence
        else:
            for i in range(0, len(sentence), max_chars):
                chunks.append(sentence[i : i + max_chars])
            current = ""
    if current:
        chunks.append(current)
    return chunks


class PollyAudioService(AudioService):
    def synthesize(self, script: str) -> Path | None:
        if not script or not script.strip():
            return None

        text = script.strip()
        chunks = _split_into_chunks(text, _MAX_CHUNK_CHARS)

        try:
            import boto3

            # Only pass explicit credential kwargs when configured - omitting
            # them (rather than passing None) lets boto3 fall back cleanly to
            # its standard credential chain (env vars, shared config, IAM
            # role) if `settings` doesn't have them.
            client_kwargs: dict = {"region_name": settings.polly_region}
            if settings.aws_access_key_id:
                client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            if settings.aws_secret_access_key:
                client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            if settings.aws_session_token:
                client_kwargs["aws_session_token"] = settings.aws_session_token

            client = boto3.client("polly", **client_kwargs)

            chunk_paths: list[Path] = []
            for chunk in chunks:
                response = client.synthesize_speech(
                    Text=chunk,
                    OutputFormat="mp3",
                    VoiceId=settings.polly_voice_id,
                    Engine=settings.polly_engine,
                )
                audio_stream = response.get("AudioStream")
                if audio_stream is None:
                    logger.error("polly_synthesis_no_audio_stream")
                    return None
                fd, path_str = tempfile.mkstemp(suffix=".mp3", prefix="narration-polly-chunk-")
                chunk_path = Path(path_str)
                with open(fd, "wb") as f:
                    f.write(audio_stream.read())
                chunk_paths.append(chunk_path)

            if len(chunk_paths) == 1:
                path = chunk_paths[0]
            else:
                path = _concat_mp3s(chunk_paths)
                for p in chunk_paths:
                    p.unlink(missing_ok=True)

            logger.info(
                "polly_synthesis_succeeded",
                bytes=path.stat().st_size,
                chunks=len(chunks),
                script_length=len(text),
            )
            return path
        except Exception as exc:  # noqa: BLE001 - Polly/network failures must never break video creation
            logger.error("polly_synthesis_failed", error=str(exc))
            return None


def _concat_mp3s(paths: list[Path]) -> Path:
    """Losslessly joins Polly mp3 chunks (all same format/bitrate/voice -
    identical encoding params, so a stream copy concat is safe and avoids
    a re-encode) via ffmpeg's concat demuxer."""
    fd, list_path_str = tempfile.mkstemp(suffix=".txt", prefix="narration-concat-list-")
    list_path = Path(list_path_str)
    with open(fd, "w") as f:
        for p in paths:
            f.write(f"file '{p.as_posix()}'\n")

    out_fd, out_path_str = tempfile.mkstemp(suffix=".mp3", prefix="narration-polly-")
    os.close(out_fd)
    out_path = Path(out_path_str)
    out_path.unlink()  # ffmpeg must create this itself

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out_path)],
        check=True,
        capture_output=True,
    )
    list_path.unlink(missing_ok=True)
    return out_path
