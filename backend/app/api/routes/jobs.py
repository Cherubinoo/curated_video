from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.repositories.job_repository import JobRepository
from app.schemas.job import RenderJobListResponse, RenderJobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=RenderJobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    video_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total = JobRepository(db).list(video_id=video_id, limit=limit, offset=offset)
    return RenderJobListResponse(items=[RenderJobResponse.model_validate(j) for j in items], total=total)


@router.get("/{job_id}", response_model=RenderJobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found")
    return RenderJobResponse.model_validate(job)
