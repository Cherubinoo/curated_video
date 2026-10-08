from __future__ import annotations

from pydantic import BaseModel

from app.schemas.job import RenderJobResponse
from app.schemas.video import VideoResponse


class DashboardStats(BaseModel):
    total: int
    draft: int
    queued: int
    processing: int
    completed: int
    failed: int


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_videos: list[VideoResponse]
    recent_jobs: list[RenderJobResponse]
