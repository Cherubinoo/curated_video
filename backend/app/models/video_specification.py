from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ValidationStatus


class VideoSpecification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "video_specifications"

    video_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    specification_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        SAEnum(ValidationStatus, name="validation_status"),
        default=ValidationStatus.PENDING,
        nullable=False,
    )
    validation_errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="specifications")
    render_jobs: Mapped[list["RenderJob"]] = relationship(back_populates="specification")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VideoSpecification video_id={self.video_id} v{self.version}>"
