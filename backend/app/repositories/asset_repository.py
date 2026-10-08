from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.enums import AssetType


class AssetRepository:
    def __init__(self, db: Session):
        self.db = db

    def latest_of_type(self, video_id: uuid.UUID, asset_type: AssetType) -> Asset | None:
        stmt = (
            select(Asset)
            .where(Asset.video_id == video_id, Asset.type == asset_type)
            .order_by(Asset.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()
