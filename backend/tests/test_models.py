from __future__ import annotations

from app.models.enums import Difficulty, RenderJobStatus, RenderStage, ValidationStatus, VideoStatus
from app.models.render_job import RenderJob
from app.models.video import Video
from app.models.video_specification import VideoSpecification
from app.services.ai.demo_specification import build_demo_specification


def test_create_video_row(db_session):
    video = Video(title="Test Video", topic="demo", prompt="p", duration=60, difficulty=Difficulty.BEGINNER)
    db_session.add(video)
    db_session.flush()

    assert video.id is not None
    assert video.status == VideoStatus.DRAFT


def test_video_specification_stores_jsonb(db_session):
    video = Video(title="T", topic="demo", prompt="p", duration=60, difficulty=Difficulty.BEGINNER)
    db_session.add(video)
    db_session.flush()

    spec = VideoSpecification(
        video_id=video.id,
        version=1,
        specification_json=build_demo_specification(),
        validation_status=ValidationStatus.VALID,
    )
    db_session.add(spec)
    db_session.flush()

    assert spec.specification_json["version"] == "1.0"
    main_scene = next(s for s in spec.specification_json["scenes"] if s["id"] == "scene_main")
    array_types = [e["type"] for e in main_scene["elements"]]
    assert "array" in array_types


def test_render_job_defaults_and_log_append(db_session):
    video = Video(title="T", topic="demo", prompt="p", duration=60, difficulty=Difficulty.BEGINNER)
    db_session.add(video)
    db_session.flush()

    job = RenderJob(video_id=video.id)
    db_session.add(job)
    db_session.flush()

    assert job.status == RenderJobStatus.PENDING
    assert job.stage == RenderStage.QUEUED
    assert job.progress == 0

    job.append_log("hello")
    job.append_log("world")
    assert "hello" in job.logs
    assert "world" in job.logs
