from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.render_job import RenderJob


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, job: RenderJob) -> RenderJob:
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: uuid.UUID) -> RenderJob | None:
        return self.db.get(RenderJob, job_id)

    def latest_for_video(self, video_id: uuid.UUID) -> RenderJob | None:
        stmt = (
            select(RenderJob)
            .where(RenderJob.video_id == video_id)
            .order_by(RenderJob.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def list(
        self, *, video_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[RenderJob], int]:
        stmt = select(RenderJob)
        if video_id is not None:
            stmt = stmt.where(RenderJob.video_id == video_id)
        total = len(self.db.execute(stmt).scalars().all())
        stmt = stmt.order_by(RenderJob.created_at.desc()).limit(limit).offset(offset)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
