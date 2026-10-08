"""draw_arrow / move_pointer / swap_elements / update_text.

These are the DSA-specific verbs the "Two Pointers"-style topics lean on
most, so they get their own module even though each is a fairly small
amount of code.
"""
from __future__ import annotations

from manim import RIGHT, Create, Text, Transform

from animation_engine.components.base import RenderContext


def draw_arrow(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        arrow = context.mobjects.get(f"{target_id}::arrow") or context.mobjects.get(target_id)
        if arrow is not None:
            animations.append(Create(arrow))
    return animations


def move_pointer(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        pointer_spec = context.elements_by_id.get(target_id)
        mobject = context.mobjects.get(target_id)
        if pointer_spec is None or mobject is None:
            continue
        array_id = getattr(pointer_spec, "target", None)
        cells = context.array_cells.get(array_id)
        if not cells or not (0 <= action.index < len(cells)):
            continue
        old_index = context.pointer_index.get(target_id, pointer_spec.index)
        old_box = cells[old_index][0]
        new_box = cells[action.index][0]
        dx = new_box.get_center()[0] - old_box.get_center()[0]
        animations.append(mobject.animate.shift(RIGHT * dx))
        context.pointer_index[target_id] = action.index
    return animations


def swap_elements(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        cells = context.array_cells.get(target_id)
        if not cells:
            continue
        i, j = action.index_a, action.index_b
        if not (0 <= i < len(cells) and 0 <= j < len(cells)):
            continue
        box_i, text_i = cells[i]
        box_j, text_j = cells[j]
        animations.append(text_i.animate.move_to(box_j.get_center()))
        animations.append(text_j.animate.move_to(box_i.get_center()))
        # The two boxes now logically hold each other's value text.
        cells[i] = (box_i, text_j)
        cells[j] = (box_j, text_i)
    return animations


def update_text(scene, context: RenderContext, action):
    animations = []
    for target_id in action.target_ids():
        old = context.mobjects.get(target_id)
        if old is None:
            continue
        spec = context.elements_by_id.get(target_id)
        color = getattr(spec, "color", "white")
        font_size = getattr(spec, "font_size", 32)
        new_mobject = Text(action.new_text, font_size=font_size, color=color)
        new_mobject.move_to(old.get_center())
        animations.append(Transform(old, new_mobject))
    return animations
