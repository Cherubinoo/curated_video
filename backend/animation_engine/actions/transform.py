"""transform: morph one already-declared element into another's shape."""
from __future__ import annotations

from manim import Transform

from animation_engine.components.base import RenderContext


def transform(scene, context: RenderContext, action):
    animations = []
    into = context.mobjects.get(action.into_element_id)
    if into is None:
        return animations
    for target_id in action.target_ids():
        current = context.mobjects.get(target_id)
        if current is not None:
            animations.append(Transform(current, into))
    return animations
