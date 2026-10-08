"""highlight / unhighlight."""
from __future__ import annotations

from animation_engine.components.base import RenderContext


def highlight(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        cells = context.array_cells.get(target_id)
        if action.index is not None and cells is not None and 0 <= action.index < len(cells):
            box, text = cells[action.index]
            animations.append(box.animate.set_color(action.color))
            animations.append(text.animate.set_color(action.color))
        else:
            mobject = context.mobjects.get(target_id)
            if mobject is not None:
                animations.append(mobject.animate.set_color(action.color))
    return animations


def unhighlight(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        cells = context.array_cells.get(target_id)
        if action.index is not None and cells is not None and 0 <= action.index < len(cells):
            box, text = cells[action.index]
            original = context.original_colors.get(f"{target_id}:{action.index}", "white")
            animations.append(box.animate.set_color(original))
            animations.append(text.animate.set_color(original))
        else:
            mobject = context.mobjects.get(target_id)
            original = context.original_colors.get(target_id, "white")
            if mobject is not None:
                animations.append(mobject.animate.set_color(original))
    return animations
