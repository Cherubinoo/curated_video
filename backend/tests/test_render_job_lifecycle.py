"""Drives the render job stage-transition lifecycle with a mocked
ManimRenderer/FFmpegService/StorageService - no real Manim render, no real
FFmpeg, no real filesystem writes. Fast, and exercises exactly the state
machine described in product spec Section 9.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import app.workers.tasks as tasks_module
from animation_engine.renderer.ffmpeg_processor import FFmpegError
from animation_engine.renderer.manim_renderer import ManimRenderError, ManimRenderResult
from app.models.enums import Difficulty, RenderJobStatus, RenderStage, ValidationStatus, VideoStatus
from app.models.render_job import RenderJob
from app.models.video import Video
from app.models.video_specification import VideoSpecification
from app.services.ai.demo_specification import build_demo_specification


def _setup_video_and_job(db_session, spec_json=None):
    video = Video(title="T", topic="demo", prompt="p", duration=60, difficulty=Difficulty.BEGINNER)
    db_session.add(video)
    db_session.flush()

    spec = VideoSpecification(
        video_id=video.id,
        version=1,
        specification_json=spec_json if spec_json is not None else build_demo_specification(),
        validation_status=ValidationStatus.VALID,
    )
    db_session.add(spec)
    db_session.flush()

    job = RenderJob(
        video_id=video.id, specification_id=spec.id, status=RenderJobStatus.PENDING, stage=RenderStage.QUEUED
    )
    db_session.add(job)
    db_session.flush()
    return video, spec, job


def _session_scope_factory(db_session):
    @contextmanager
    def _scope():
        yield db_session

    return _scope


def test_successful_render_job_reaches_completed(db_session, tmp_path):
    video, spec, job = _setup_video_and_job(db_session)

    fake_video_file = tmp_path / "rendered.mp4"
    fake_video_file.write_bytes(b"fake mp4 bytes")

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
        patch.object(tasks_module, "FFmpegService") as MockFFmpeg,
        patch.object(tasks_module, "get_storage_service") as mock_get_storage,
    ):
        MockRenderer.return_value.render.return_value = ManimRenderResult(
            video_path=fake_video_file, logs="manim ok"
        )
        MockFFmpeg.return_value.finalize.return_value = "ffmpeg ok"
        MockFFmpeg.return_value.generate_thumbnail.return_value = "thumb ok"

        mock_storage = MagicMock()
        mock_storage.save.side_effect = lambda key, path: key
        mock_storage.save_bytes.side_effect = lambda key, data: key
        mock_storage.get_url.side_effect = lambda key: f"http://localhost:8000/media/{key}"
        mock_get_storage.return_value = mock_storage

        tasks_module.render_video_task(str(job.id))

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.COMPLETED
    assert job.stage == RenderStage.COMPLETED
    assert job.progress == 100
    assert video.status == VideoStatus.COMPLETED
    assert video.video_url is not None
    assert video.thumbnail_url is not None


def test_invalid_specification_fails_the_job_without_rendering(db_session):
    broken_spec = {"version": "1.0"}  # missing required fields
    video, spec, job = _setup_video_and_job(db_session, spec_json=broken_spec)

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
    ):
        tasks_module.render_video_task(str(job.id))
        MockRenderer.return_value.render.assert_not_called()

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.FAILED
    assert job.stage == RenderStage.FAILED
    assert video.status == VideoStatus.FAILED
    assert job.error_message is not None


def test_manim_failure_marks_job_failed_without_crashing(db_session):
    video, spec, job = _setup_video_and_job(db_session)

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
    ):
        MockRenderer.return_value.render.side_effect = ManimRenderError("boom", logs="manim exploded")

        # Must not raise - a render failure fails the job, it never crashes
        # the calling worker process.
        tasks_module.render_video_task(str(job.id))

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.FAILED
    assert "Manim rendering failed" in job.error_message
    assert video.status == VideoStatus.FAILED


def test_ffmpeg_failure_marks_job_failed(db_session, tmp_path):
    video, spec, job = _setup_video_and_job(db_session)
    fake_video_file = tmp_path / "rendered.mp4"
    fake_video_file.write_bytes(b"fake mp4 bytes")

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
        patch.object(tasks_module, "FFmpegService") as MockFFmpeg,
    ):
        MockRenderer.return_value.render.return_value = ManimRenderResult(
            video_path=fake_video_file, logs="manim ok"
        )
        MockFFmpeg.return_value.finalize.side_effect = FFmpegError("ffmpeg boom", logs="ffmpeg exploded")

        tasks_module.render_video_task(str(job.id))

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.FAILED
    assert "post-processing failed" in job.error_message
    assert video.status == VideoStatus.FAILED


def test_synced_assembly_used_when_scenes_have_their_own_narration(db_session, tmp_path):
    """The preferred path: each scene's own narration is synthesized and
    synced to that scene's actual rendered timing (see ManimRenderResult.
    scene_timeline / FFmpegService.assemble_synced_video), instead of one
    whole-video narration track that can drift out of sync over a long
    video - a real observed bug ("video going somewhere, audio somewhere
    else")."""
    spec_json = build_demo_specification(narration="top-level fallback narration", voice_provider="polly")
    spec_json["scenes"][1]["narration"] = "This scene has its own narration."  # "scene_main"
    video, spec, job = _setup_video_and_job(db_session, spec_json=spec_json)

    fake_video_file = tmp_path / "rendered.mp4"
    fake_video_file.write_bytes(b"fake mp4 bytes")

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
        patch.object(tasks_module, "FFmpegService") as MockFFmpeg,
        patch.object(tasks_module, "get_audio_service") as mock_get_audio,
        patch.object(tasks_module, "get_storage_service") as mock_get_storage,
    ):
        MockRenderer.return_value.render.return_value = ManimRenderResult(
            video_path=fake_video_file,
            logs="manim ok",
            scene_timeline=[
                {"id": "scene_intro", "start": 0.0, "end": 4.5},
                {"id": "scene_main", "start": 4.5, "end": 20.5},
                {"id": "scene_outro", "start": 20.5, "end": 26.0},
            ],
        )
        fake_audio = tmp_path / "narration.mp3"
        fake_audio.write_bytes(b"fake mp3 bytes")
        mock_audio_service = MagicMock()
        mock_audio_service.synthesize.return_value = fake_audio
        mock_get_audio.return_value = mock_audio_service

        MockFFmpeg.return_value.assemble_synced_video.return_value = "assembly ok"
        MockFFmpeg.return_value.generate_thumbnail.return_value = "thumb ok"

        mock_storage = MagicMock()
        mock_storage.save.side_effect = lambda key, path: key
        mock_storage.save_bytes.side_effect = lambda key, data: key
        mock_storage.get_url.side_effect = lambda key: f"http://localhost:8000/media/{key}"
        mock_get_storage.return_value = mock_storage

        tasks_module.render_video_task(str(job.id))

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.COMPLETED
    assert video.status == VideoStatus.COMPLETED
    # Only the scene with its own narration ("scene_main") should have
    # triggered a synthesize() call, not all three.
    assert mock_audio_service.synthesize.call_count == 1
    assert mock_audio_service.synthesize.call_args.args[0] == "This scene has its own narration."
    MockFFmpeg.return_value.assemble_synced_video.assert_called_once()
    MockFFmpeg.return_value.finalize.assert_not_called()


def test_falls_back_to_whole_video_narration_when_no_scene_has_its_own(db_session, tmp_path):
    """A scene_timeline exists but no individual scene carries narration
    (e.g. an older spec, or one where per-scene narration wasn't set) -
    must fall back to the single whole-video narration track rather than
    silently producing a mute video."""
    spec_json = build_demo_specification()  # no narration arg - no scene gets its own narration either
    for scene in spec_json["scenes"]:
        scene["narration"] = None
    spec_json["audio"] = {
        "enabled": True,
        "narration_script": "top-level fallback narration",
        "voice_provider": "polly",
    }
    video, spec, job = _setup_video_and_job(db_session, spec_json=spec_json)

    fake_video_file = tmp_path / "rendered.mp4"
    fake_video_file.write_bytes(b"fake mp4 bytes")

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
        patch.object(tasks_module, "FFmpegService") as MockFFmpeg,
        patch.object(tasks_module, "get_audio_service") as mock_get_audio,
        patch.object(tasks_module, "get_storage_service") as mock_get_storage,
    ):
        MockRenderer.return_value.render.return_value = ManimRenderResult(
            video_path=fake_video_file,
            logs="manim ok",
            scene_timeline=[
                {"id": "scene_intro", "start": 0.0, "end": 4.5},
                {"id": "scene_main", "start": 4.5, "end": 20.5},
                {"id": "scene_outro", "start": 20.5, "end": 26.0},
            ],
        )
        fake_audio = tmp_path / "narration.mp3"
        fake_audio.write_bytes(b"fake mp3 bytes")
        mock_audio_service = MagicMock()
        mock_audio_service.synthesize.return_value = fake_audio
        mock_get_audio.return_value = mock_audio_service

        MockFFmpeg.return_value.finalize.return_value = "ffmpeg ok"
        MockFFmpeg.return_value.generate_thumbnail.return_value = "thumb ok"

        mock_storage = MagicMock()
        mock_storage.save.side_effect = lambda key, path: key
        mock_storage.save_bytes.side_effect = lambda key, data: key
        mock_storage.get_url.side_effect = lambda key: f"http://localhost:8000/media/{key}"
        mock_get_storage.return_value = mock_storage

        tasks_module.render_video_task(str(job.id))

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.COMPLETED
    MockFFmpeg.return_value.assemble_synced_video.assert_not_called()
    MockFFmpeg.return_value.finalize.assert_called_once()
    assert mock_audio_service.synthesize.call_args.args[0] == "top-level fallback narration"


def test_synced_assembly_failure_falls_back_to_whole_video_narration(db_session, tmp_path):
    """A render must never fail just because the newer per-scene sync step
    hit a problem - fall back to the proven whole-video path rather than
    failing the job."""
    spec_json = build_demo_specification(narration="top-level fallback narration", voice_provider="polly")
    spec_json["scenes"][1]["narration"] = "This scene has its own narration."
    video, spec, job = _setup_video_and_job(db_session, spec_json=spec_json)

    fake_video_file = tmp_path / "rendered.mp4"
    fake_video_file.write_bytes(b"fake mp4 bytes")

    with (
        patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)),
        patch.object(tasks_module, "ManimRenderer") as MockRenderer,
        patch.object(tasks_module, "FFmpegService") as MockFFmpeg,
        patch.object(tasks_module, "get_audio_service") as mock_get_audio,
        patch.object(tasks_module, "get_storage_service") as mock_get_storage,
    ):
        MockRenderer.return_value.render.return_value = ManimRenderResult(
            video_path=fake_video_file,
            logs="manim ok",
            scene_timeline=[
                {"id": "scene_intro", "start": 0.0, "end": 4.5},
                {"id": "scene_main", "start": 4.5, "end": 20.5},
                {"id": "scene_outro", "start": 20.5, "end": 26.0},
            ],
        )
        fake_audio = tmp_path / "narration.mp3"
        fake_audio.write_bytes(b"fake mp3 bytes")
        mock_audio_service = MagicMock()
        mock_audio_service.synthesize.return_value = fake_audio
        mock_get_audio.return_value = mock_audio_service

        MockFFmpeg.return_value.assemble_synced_video.side_effect = FFmpegError("boom", logs="assembly exploded")
        MockFFmpeg.return_value.finalize.return_value = "ffmpeg ok"
        MockFFmpeg.return_value.generate_thumbnail.return_value = "thumb ok"

        mock_storage = MagicMock()
        mock_storage.save.side_effect = lambda key, path: key
        mock_storage.save_bytes.side_effect = lambda key, data: key
        mock_storage.get_url.side_effect = lambda key: f"http://localhost:8000/media/{key}"
        mock_get_storage.return_value = mock_storage

        tasks_module.render_video_task(str(job.id))

    db_session.refresh(job)
    db_session.refresh(video)

    assert job.status == RenderJobStatus.COMPLETED
    MockFFmpeg.return_value.assemble_synced_video.assert_called_once()
    MockFFmpeg.return_value.finalize.assert_called_once()


def test_missing_job_is_a_noop_not_a_crash(db_session):
    with patch.object(tasks_module, "session_scope", _session_scope_factory(db_session)):
        # Should log and return quietly rather than raising.
        tasks_module.render_video_task("00000000-0000-0000-0000-000000000000")
