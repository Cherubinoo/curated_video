from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RenderJobStatus, RenderStage


class RenderJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    specification_id: uuid.UUID | None
    status: RenderJobStatus
    progress: int
    stage: RenderStage
    logs: str
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RenderJobListResponse(BaseModel):
    items: list[RenderJobResponse]
    total: int
