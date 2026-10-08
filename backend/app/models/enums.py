"""Enums shared by SQLAlchemy models and Pydantic schemas.

Kept as plain `str, Enum` classes so they serialize cleanly to JSON and can
be reused directly as Pydantic field types as well as SQLAlchemy `Enum`
columns.
"""
from __future__ import annotations

import enum


class VideoStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RenderJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RenderStage(str, enum.Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    GENERATING_ANIMATION = "GENERATING_ANIMATION"
    RENDERING_MANIM = "RENDERING_MANIM"
    PROCESSING_VIDEO = "PROCESSING_VIDEO"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Difficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"


class AssetType(str, enum.Enum):
    SPECIFICATION = "SPECIFICATION"
    ANIMATION_VIDEO = "ANIMATION_VIDEO"
    AUDIO = "AUDIO"
    FINAL_VIDEO = "FINAL_VIDEO"
    SUBTITLES = "SUBTITLES"
    THUMBNAIL = "THUMBNAIL"
    PREVIEW = "PREVIEW"
