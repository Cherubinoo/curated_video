from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.enums import RenderStage, VideoStatus
from app.repositories.job_repository import JobRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.video import VideoStatusResponse
from app.services.exceptions import VideoNotFoundError


class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.jobs = JobRepository(db)
        self.videos = VideoRepository(db)

    def get_video_status(self, video_id: uuid.UUID) -> VideoStatusResponse:
        video = self.videos.get(video_id)
        if video is None:
            raise VideoNotFoundError(video_id)

        job = self.jobs.latest_for_video(video_id)
        if job is None:
            return VideoStatusResponse(status=video.status, progress=0, stage=None)

        return VideoStatusResponse(
            status=video.status,
            progress=job.progress,
            stage=job.stage.value if isinstance(job.stage, RenderStage) else job.stage,
        )
