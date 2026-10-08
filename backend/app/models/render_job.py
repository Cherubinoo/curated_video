from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RenderJobStatus, RenderStage


class RenderJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "render_jobs"

    video_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    specification_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("video_specifications.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[RenderJobStatus] = mapped_column(
        SAEnum(RenderJobStatus, name="render_job_status"),
        default=RenderJobStatus.PENDING,
        nullable=False,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[RenderStage] = mapped_column(
        SAEnum(RenderStage, name="render_stage"), default=RenderStage.QUEUED, nullable=False
    )
    logs: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    video: Mapped["Video"] = relationship(back_populates="render_jobs")
    specification: Mapped["VideoSpecification | None"] = relationship(back_populates="render_jobs")

    def append_log(self, message: str) -> None:
        """Append a timestamped line to the job log. Callers are responsible
        for committing the session afterwards."""
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.logs = f"{self.logs}[{ts}] {message}\n"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RenderJob video_id={self.video_id} stage={self.stage} progress={self.progress}>"
