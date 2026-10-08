"""API request/response DTOs for videos. Distinct from the VideoSpecification
DSL in `app.schemas.specification` - these describe the *API contract*, not
the animation content."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Difficulty, VideoStatus


class VideoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    topic: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=20000)
    duration: int = Field(gt=0, le=600, description="Target duration in seconds")
    difficulty: Difficulty = Difficulty.BEGINNER
    notes: str | None = Field(default=None, max_length=5000)


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    topic: str
    prompt: str
    notes: str | None
    status: VideoStatus
    duration: int
    difficulty: Difficulty
    video_url: str | None
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime


class VideoRegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Free-text feedback from the admin ("make the title punchier", "focus
    # more on X") folded into the prompt sent to the specification
    # generator for this regeneration only. Also appended to the video's
    # notes for a durable record of what was asked for.
    suggestions: str | None = Field(default=None, max_length=5000)


class PromptExpandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=255)
    # Matches VideoCreateRequest.prompt's limit - a real observed crash had
    # an admin write a genuinely detailed, multi-section description (the
    # 17-point content outline invites exactly this) that exceeded the old
    # 2000-char cap. That was a much lower limit than `prompt` allows for
    # no good reason, since the description effectively becomes the prompt
    # in the auto-generation flow.
    description: str = Field(min_length=1, max_length=20000)


class PromptExpandResponse(BaseModel):
    prompt: str


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int


class VideoCreateResponse(BaseModel):
    id: uuid.UUID
    status: VideoStatus


class VideoStatusResponse(BaseModel):
    status: VideoStatus
    progress: int
    stage: str | None
