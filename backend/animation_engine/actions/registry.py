"""Action-type -> executor registry, and the single `execute_action()` entry
point the scene builder calls. Adding a new action means writing one
function and adding one line here."""
from __future__ import annotations

from animation_engine.actions import camera, code_ops, highlight, motion, pointer_ops, transform, visibility
from animation_engine.components.base import RenderContext

ACTION_REGISTRY = {
    "create": visibility.create,
    "show": visibility.show,
    "hide": visibility.hide,
    "write": visibility.write,
    "fade_in": visibility.fade_in,
    "fade_out": visibility.fade_out,
    "move": motion.move,
    "shift": motion.shift,
    "scale": motion.scale,
    "rotate": motion.rotate,
    "highlight": highlight.highlight,
    "unhighlight": highlight.unhighlight,
    "transform": transform.transform,
    "wait": lambda scene, context, action: [],
    "draw_arrow": pointer_ops.draw_arrow,
    "move_pointer": pointer_ops.move_pointer,
    "swap_elements": pointer_ops.swap_elements,
    "update_text": pointer_ops.update_text,
    "highlight_code_line": code_ops.highlight_code_line,
    "camera_zoom": camera.camera_zoom,
    "camera_pan": camera.camera_pan,
}


def execute_action(scene, context: RenderContext, action) -> None:
    executor = ACTION_REGISTRY.get(action.type)
    if executor is None:
        raise ValueError(f"No executor registered for action type {action.type!r}")

    animations = executor(scene, context, action) or []
    if animations:
        scene.play(*animations, run_time=action.duration)
    elif action.duration > 0:
        scene.wait(action.duration)

    if action.wait_after > 0:
        scene.wait(action.wait_after)
