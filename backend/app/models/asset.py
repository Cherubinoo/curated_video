from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AssetType


class Asset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assets"

    video_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[AssetType] = mapped_column(SAEnum(AssetType, name="asset_type"), nullable=False)
    # Storage-relative key (e.g. "videos/{id}/versions/1/final.mp4"), never an
    # absolute filesystem path - see app.services.storage.path_utils.
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Mapped to DB column "metadata"; the Python attribute is named `meta` to
    # avoid colliding with SQLAlchemy's declarative `Base.metadata`.
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="assets")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Asset {self.type} path={self.path!r}>"
