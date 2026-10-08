import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.models.enums import AssetType, VideoStatus
from app.repositories.asset_repository import AssetRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.job import RenderJobResponse
from app.schemas.video import (
    PromptExpandRequest,
    PromptExpandResponse,
    VideoCreateRequest,
    VideoCreateResponse,
    VideoListResponse,
    VideoRegenerateRequest,
    VideoResponse,
    VideoStatusResponse,
)
from app.services.ai.prompt_expander import get_prompt_expander
from app.services.ai.specification_generator import SpecificationGenerationError
from app.services.exceptions import VideoActiveError, VideoNotFoundError
from app.services.job_service import JobService
from app.services.storage.factory import get_storage_service
from app.services.video_service import VideoService

logger = get_logger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=VideoCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_video(request: Request, payload: VideoCreateRequest, db: Session = Depends(get_db)):
    video = VideoService(db).create_video(payload)
    return VideoCreateResponse(id=video.id, status=video.status)


@router.post("/expand-prompt", response_model=PromptExpandResponse)
@limiter.limit("20/minute")
def expand_prompt(request: Request, payload: PromptExpandRequest):
    """Turns a short topic + description into a detailed prompt the admin
    can review/edit before creating a video. Never fails outright - falls
    back to a deterministic template if no AI provider is configured or the
    call errors (see PromptExpander.expand)."""
    expander = get_prompt_expander()
    prompt = expander.expand(payload.topic, payload.description)
    return PromptExpandResponse(prompt=prompt)


@router.get("", response_model=VideoListResponse)
def list_videos(
    db: Session = Depends(get_db),
    status_filter: VideoStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total = VideoRepository(db).list(status=status_filter, limit=limit, offset=offset)
    return VideoListResponse(items=[VideoResponse.model_validate(v) for v in items], total=total)


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    video = VideoRepository(db).get(video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return VideoResponse.model_validate(video)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def delete_video(request: Request, video_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        VideoService(db).delete_video(video_id)
    except VideoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    except VideoActiveError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a video while it is queued or processing. Wait for it to finish first.",
        )


@router.post("/{video_id}/generate", response_model=RenderJobResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
def generate_video(request: Request, video_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        job = VideoService(db).trigger_render(video_id)
    except VideoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    except SpecificationGenerationError as exc:
        logger.error("generate_video_failed", video_id=str(video_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not generate a valid video specification for this prompt.",
        )
    return RenderJobResponse.model_validate(job)


@router.get("/{video_id}/status", response_model=VideoStatusResponse)
def get_video_status(video_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return JobService(db).get_video_status(video_id)
    except VideoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")


@router.post("/{video_id}/regenerate", response_model=RenderJobResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
def regenerate_video(
    request: Request,
    video_id: uuid.UUID,
    payload: VideoRegenerateRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = VideoService(db).trigger_render(
            video_id, suggestions=payload.suggestions if payload else None
        )
    except VideoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    except SpecificationGenerationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not generate a valid video specification for this prompt.",
        )
    return RenderJobResponse.model_validate(job)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "video"


@router.get("/{video_id}/download")
def download_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    """Streams the final MP4 as a proper attachment (Content-Disposition)
    so the browser saves it locally with a friendly filename, rather than
    just playing it inline."""
    video = VideoRepository(db).get(video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    asset = AssetRepository(db).latest_of_type(video_id, AssetType.FINAL_VIDEO)
    if asset is None or video.status != VideoStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed video available yet")

    local_path = get_storage_service().open(asset.path)
    if not local_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found in storage")

    filename = f"{_slugify(video.title)}.mp4"
    return FileResponse(path=local_path, media_type="video/mp4", filename=filename)
