"""Top-level VideoSpecification - the contract between the (future) AI
specification generator and the animation engine. Nothing downstream of
`validate_specification()` ever trusts unvalidated JSON."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.specification.common import DSLBaseModel, validate_color
from app.schemas.specification.scene import Scene


class Metadata(DSLBaseModel):
    title: str = Field(min_length=1, max_length=255)
    topic: str = Field(min_length=1, max_length=255)
    duration_target: int = Field(gt=0, le=600)  # seconds
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"


class CanvasSettings(DSLBaseModel):
    width: int = Field(default=1920, ge=320, le=3840)
    height: int = Field(default=1080, ge=240, le=2160)
    fps: int = Field(default=30, ge=1, le=120)
    background_color: str = "#0e1116"

    _validate_color = field_validator("background_color")(validate_color)


class AudioConfig(DSLBaseModel):
    enabled: bool = False
    narration_script: str | None = Field(default=None, max_length=10000)
    voice_provider: Literal["none", "upload", "elevenlabs", "polly"] = "none"
    audio_asset_path: str | None = None


class SubtitleConfig(DSLBaseModel):
    enabled: bool = False
    provider: Literal["none", "whisper", "upload"] = "none"
    subtitle_asset_path: str | None = None


class AssetRef(DSLBaseModel):
    id: str
    type: Literal["image", "audio", "font", "other"]
    path: str = Field(max_length=1024)


class VideoSpecification(DSLBaseModel):
    version: Literal["1.0"] = "1.0"
    metadata: Metadata
    settings: CanvasSettings = Field(default_factory=CanvasSettings)
    scenes: list[Scene] = Field(min_length=1, max_length=50)
    assets: list[AssetRef] = Field(default_factory=list)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    subtitles: SubtitleConfig = Field(default_factory=SubtitleConfig)

    @model_validator(mode="after")
    def _validate_scene_ids_unique(self) -> "VideoSpecification":
        seen: set[str] = set()
        for scene in self.scenes:
            if scene.id in seen:
                raise ValueError(f"duplicate scene id {scene.id!r}")
            seen.add(scene.id)
        return self

    def total_duration(self) -> float:
        return sum(scene.duration for scene in self.scenes)

    def all_warnings(self) -> list[str]:
        return [w for scene in self.scenes for w in scene.warnings]
