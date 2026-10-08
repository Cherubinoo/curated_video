from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import VideoStatus
from app.models.video import Video
from app.models.video_specification import VideoSpecification


class VideoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, video: Video) -> Video:
        self.db.add(video)
        self.db.flush()
        return video

    def get(self, video_id: uuid.UUID) -> Video | None:
        return self.db.get(Video, video_id)

    def list(
        self, *, status: VideoStatus | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Video], int]:
        stmt = select(Video)
        if status is not None:
            stmt = stmt.where(Video.status == status)
        total = len(self.db.execute(stmt).scalars().all())
        stmt = stmt.order_by(Video.created_at.desc()).limit(limit).offset(offset)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def next_specification_version(self, video_id: uuid.UUID) -> int:
        stmt = select(VideoSpecification.version).where(VideoSpecification.video_id == video_id)
        versions = self.db.execute(stmt).scalars().all()
        return (max(versions) + 1) if versions else 1

    def latest_specification(self, video_id: uuid.UUID) -> VideoSpecification | None:
        stmt = (
            select(VideoSpecification)
            .where(VideoSpecification.video_id == video_id)
            .order_by(VideoSpecification.version.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def counts_by_status(self) -> dict[str, int]:
        stmt = select(Video.status)
        rows = self.db.execute(stmt).scalars().all()
        counts = {status.value: 0 for status in VideoStatus}
        for status in rows:
            counts[status.value] = counts.get(status.value, 0) + 1
        return counts
