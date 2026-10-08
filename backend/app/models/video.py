from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import Difficulty, VideoStatus


class Video(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "videos"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Free text on purpose: the 18 topics are a frontend convenience list, not
    # a hardcoded backend constraint, so new topics never need a migration.
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[VideoStatus] = mapped_column(
        SAEnum(VideoStatus, name="video_status"), default=VideoStatus.DRAFT, nullable=False
    )
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # target seconds
    difficulty: Mapped[Difficulty] = mapped_column(
        SAEnum(Difficulty, name="difficulty"), default=Difficulty.BEGINNER, nullable=False
    )

    video_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, nullable=False
    )

    specifications: Mapped[list["VideoSpecification"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="VideoSpecification.version"
    )
    render_jobs: Mapped[list["RenderJob"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="RenderJob.created_at"
    )
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Video {self.title!r} status={self.status}>"
