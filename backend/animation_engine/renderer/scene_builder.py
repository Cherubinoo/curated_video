"""The one and only Manim Scene class in this system. It is fixed, reviewed
code - it never executes anything the AI/prompt layer produced directly.
All it does is read a validated VideoSpecification JSON file (path given via
an environment variable set by ManimRenderer) and replay it through the
component/action registries.

This is what makes "no arbitrary AI-generated Python" true in practice: the
JSON varies, this file does not.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from manim import MovingCameraScene

from animation_engine.actions.registry import execute_action
from animation_engine.components.base import RenderContext
from animation_engine.components.registry import build_scene_elements
from animation_engine.validators.specification_validator import validate_specification

SPEC_PATH_ENV = "DSA_SPEC_PATH"
PROGRESS_PATH_ENV = "DSA_PROGRESS_PATH"
TIMELINE_PATH_ENV = "DSA_TIMELINE_PATH"


class SpecificationScene(MovingCameraScene):
    def construct(self) -> None:
        spec_path = os.environ.get(SPEC_PATH_ENV)
        if not spec_path:
            raise RuntimeError(
                f"{SPEC_PATH_ENV} environment variable not set - SpecificationScene must be "
                "invoked via animation_engine.renderer.manim_renderer.ManimRenderer."
            )

        raw = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        result = validate_specification(raw)
        if not result.is_valid:
            raise ValueError(
                "SpecificationScene received an invalid VideoSpecification: " + "; ".join(result.errors)
            )
        spec = result.specification

        self.camera.background_color = spec.settings.background_color

        default_frame_center = self.camera.frame.get_center().copy()
        default_frame_width = self.camera.frame.width

        progress_path = os.environ.get(PROGRESS_PATH_ENV)
        timeline: list[dict] = []

        for scene_index, scene in enumerate(spec.scenes):
            scene_start = self.renderer.time
            context = RenderContext(elements_by_id={el.id: el for el in scene.elements})
            build_scene_elements(scene.elements, context)

            for action in scene.actions:
                execute_action(self, context, action)

            timeline.append({"id": scene.id, "start": scene_start, "end": self.renderer.time})
            self._write_progress(progress_path, scene_index + 1, len(spec.scenes))

            self.clear()
            self.camera.frame.move_to(default_frame_center)
            self.camera.frame.set(width=default_frame_width)

        self._write_timeline(os.environ.get(TIMELINE_PATH_ENV), timeline)

    @staticmethod
    def _write_progress(progress_path: str | None, scene_index: int, total_scenes: int) -> None:
        if not progress_path:
            return
        try:
            Path(progress_path).write_text(
                json.dumps({"scene_index": scene_index, "total_scenes": total_scenes}),
                encoding="utf-8",
            )
        except OSError:
            pass  # progress reporting is best-effort, never fails the render

    @staticmethod
    def _write_timeline(timeline_path: str | None, timeline: list[dict]) -> None:
        """Records each scene's exact rendered start/end time (in seconds,
        from Manim's own `renderer.time` clock) so the worker can later
        synthesize and align each scene's own narration to precisely when
        that scene actually plays, instead of relying only on the model's
        pacing estimate - see workers/tasks.py and
        animation_engine/renderer/ffmpeg_processor.py's per-scene assembly."""
        if not timeline_path:
            return
        try:
            Path(timeline_path).write_text(json.dumps(timeline), encoding="utf-8")
        except OSError:
            pass  # best-effort, same as progress reporting - never fails the render
