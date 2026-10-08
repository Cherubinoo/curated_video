"""camera_zoom / camera_pan.

Requires the scene to be a Manim `MovingCameraScene` (SpecificationScene
always is - see animation_engine/renderer/scene_builder.py).
"""
from __future__ import annotations

from animation_engine.components.base import RenderContext


def camera_zoom(scene, context: RenderContext, action):
    frame = getattr(scene.camera, "frame", None)
    if frame is None:
        return []
    return [frame.animate.scale(action.scale)]


def camera_pan(scene, context: RenderContext, action):
    frame = getattr(scene.camera, "frame", None)
    if frame is None:
        return []
    target_pos = context.resolve_position(action.to)
    return [frame.animate.move_to(target_pos)]
