from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.repositories.job_repository import JobRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.dashboard import DashboardResponse, DashboardStats
from app.schemas.job import RenderJobResponse
from app.schemas.video import VideoResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    videos = VideoRepository(db)
    jobs = JobRepository(db)

    counts = videos.counts_by_status()
    stats = DashboardStats(
        total=sum(counts.values()),
        draft=counts.get("DRAFT", 0),
        queued=counts.get("QUEUED", 0),
        processing=counts.get("PROCESSING", 0),
        completed=counts.get("COMPLETED", 0),
        failed=counts.get("FAILED", 0),
    )

    recent_videos, _ = videos.list(limit=10, offset=0)
    recent_jobs, _ = jobs.list(limit=10, offset=0)

    return DashboardResponse(
        stats=stats,
        recent_videos=[VideoResponse.model_validate(v) for v in recent_videos],
        recent_jobs=[RenderJobResponse.model_validate(j) for j in recent_jobs],
    )
