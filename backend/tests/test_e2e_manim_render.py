"""The first real end-to-end test (product spec Section 20/21): validate the
bundled demo specification, render it with the *actual* Manim CLI (real
subprocess, real FFmpeg post-processing), and assert a valid, non-empty MP4
comes out the other end.

This only runs where `manim` and `ffmpeg` are actually installed - i.e. the
video-worker image, not the API backend image. Run it with:

    docker compose exec video-worker pytest tests/test_e2e_manim_render.py -m e2e -v

It is slow (a real render), so it is not part of the default fast test run.
"""
from __future__ import annotations

import shutil

import pytest

from animation_engine.renderer.ffmpeg_processor import FFmpegService
from animation_engine.renderer.manim_renderer import ManimRenderer
from animation_engine.validators.specification_validator import validate_specification
from app.services.ai.demo_specification import build_demo_specification

pytestmark = pytest.mark.e2e

_MANIM_AVAILABLE = shutil.which("manim") is not None
_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _MANIM_AVAILABLE, reason="manim CLI not on PATH - run this inside video-worker")
@pytest.mark.skipif(not _FFMPEG_AVAILABLE, reason="ffmpeg not on PATH - run this inside video-worker")
def test_full_pipeline_renders_a_real_mp4(tmp_path):
    raw_spec = build_demo_specification(title="E2E Test", topic="platform-demo", duration_target=10)

    result = validate_specification(raw_spec)
    assert result.is_valid, result.errors
    specification = result.specification

    renderer = ManimRenderer(timeout_seconds=180)
    seen_progress = []
    render_result = renderer.render(
        specification,
        tmp_path / "manim",
        progress_callback=lambda i, total: seen_progress.append((i, total)),
    )

    assert render_result.video_path.exists()
    assert render_result.video_path.stat().st_size > 1000  # not an empty/corrupt file
    assert seen_progress  # at least one scene reported progress

    ffmpeg = FFmpegService()
    final_path = tmp_path / "final.mp4"
    thumbnail_path = tmp_path / "thumbnail.jpg"
    ffmpeg.finalize(
        render_result.video_path,
        final_path,
        width=specification.settings.width,
        height=specification.settings.height,
        fps=specification.settings.fps,
    )
    ffmpeg.generate_thumbnail(final_path, thumbnail_path)

    assert final_path.exists()
    assert final_path.stat().st_size > 1000
    assert thumbnail_path.exists()
