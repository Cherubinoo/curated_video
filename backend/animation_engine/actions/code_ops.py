"""highlight_code_line."""
from __future__ import annotations

from animation_engine.components.base import RenderContext


def highlight_code_line(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        lines = context.code_lines.get(target_id, [])
        if 0 <= action.line_number < len(lines):
            _, rect = lines[action.line_number]
            animations.append(
                rect.animate.set_stroke(color=action.color, opacity=1).set_fill(
                    color=action.color, opacity=0.15
                )
            )
    return animations
