"""Orchestrates video creation and render-job creation. This is the only
layer that knows how to go from "an API request" to "a queued Celery task" -
API routes stay thin, the worker stays independent."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.enums import RenderJobStatus, RenderStage, ValidationStatus, VideoStatus
from app.models.render_job import RenderJob
from app.models.video import Video
from app.models.video_specification import VideoSpecification
from app.repositories.job_repository import JobRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.video import VideoCreateRequest
from app.services.ai.specification_generator import (
    SpecificationGenerationError,
    get_specification_generator,
)
from app.services.exceptions import VideoActiveError, VideoNotFoundError
from app.services.storage.factory import get_storage_service

logger = get_logger(__name__)


class VideoService:
    def __init__(self, db: Session):
        self.db = db
        self.videos = VideoRepository(db)
        self.jobs = JobRepository(db)

    def create_video(self, payload: VideoCreateRequest) -> Video:
        video = Video(
            title=payload.title,
            topic=payload.topic,
            prompt=payload.prompt,
            notes=payload.notes,
            duration=payload.duration,
            difficulty=payload.difficulty,
            status=VideoStatus.DRAFT,
        )
        self.videos.create(video)
        self.db.commit()
        self.db.refresh(video)
        logger.info("video_created", video_id=str(video.id), title=video.title)
        return video

    def trigger_render(self, video_id: uuid.UUID, *, suggestions: str | None = None) -> RenderJob:
        """Used by both POST /generate and POST /regenerate: resolves a
        VideoSpecification for the video's stored prompt (optionally
        amended with admin `suggestions` from the regenerate flow),
        validates it, persists a new version, creates a RenderJob, and
        enqueues it."""
        video = self.videos.get(video_id)
        if video is None:
            raise VideoNotFoundError(video_id)

        generator_prompt = video.prompt
        if suggestions:
            generator_prompt = (
                f"{video.prompt}\n\nAdditional updates/suggestions from the admin for this "
                f"regeneration:\n{suggestions}"
            )
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            note_line = f"[Regenerate suggestion @ {timestamp}]: {suggestions}"
            video.notes = f"{video.notes}\n\n{note_line}" if video.notes else note_line

        generator = get_specification_generator()
        try:
            spec = generator.generate_specification(
                generator_prompt,
                title=video.title,
                topic=video.topic,
                duration_target=video.duration,
            )
        except SpecificationGenerationError:
            logger.error("specification_generation_failed", video_id=str(video.id))
            raise

        version = self.videos.next_specification_version(video.id)
        spec_row = VideoSpecification(
            video_id=video.id,
            version=version,
            specification_json=spec.model_dump(mode="json"),
            validation_status=ValidationStatus.VALID,
            validation_errors=None,
        )
        self.db.add(spec_row)
        self.db.flush()

        job = RenderJob(
            video_id=video.id,
            specification_id=spec_row.id,
            status=RenderJobStatus.PENDING,
            stage=RenderStage.QUEUED,
        )
        self.jobs.create(job)
        job.append_log(f"Job created for specification v{version}.")

        video.status = VideoStatus.QUEUED
        self.db.commit()
        self.db.refresh(job)

        # Imported lazily to avoid import-time coupling between the API
        # process and Celery task registration order.
        from app.workers.tasks import render_video_task

        async_result = render_video_task.delay(str(job.id))
        job.celery_task_id = async_result.id
        self.db.commit()

        logger.info("render_job_queued", video_id=str(video.id), job_id=str(job.id), version=version)
        return job

    def delete_video(self, video_id: uuid.UUID) -> None:
        """Permanently deletes a video: its DB row (VideoSpecification,
        RenderJob, and Asset rows cascade via FK ondelete=CASCADE) and every
        file under its `videos/{video_id}` storage prefix, all versions
        included. Refused while a render is queued/running - the worker
        holds a live reference to the row and would otherwise crash trying
        to update a video that no longer exists."""
        video = self.videos.get(video_id)
        if video is None:
            raise VideoNotFoundError(video_id)

        if video.status in (VideoStatus.QUEUED, VideoStatus.PROCESSING):
            raise VideoActiveError(video_id)

        get_storage_service().delete_prefix(f"videos/{video_id}")

        self.db.delete(video)
        self.db.commit()
        logger.info("video_deleted", video_id=str(video_id))
