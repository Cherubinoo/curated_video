from __future__ import annotations

from manim import UP, Arrow, Text, VGroup

from animation_engine.components.base import RenderContext, SceneComponent


class PointerComponent(SceneComponent):
    """Builds a downward-pointing arrow + label above one cell of an
    already-built ArrayElement. Must build after the array (build_priority)."""

    build_priority = 1

    def build(self, element, context: RenderContext) -> VGroup:
        cells = context.array_cells.get(element.target)
        if not cells:
            raise ValueError(
                f"pointer {element.id!r} references array {element.target!r}, "
                "which was not built (build order bug or invalid reference)."
            )
        box, _ = cells[element.index]

        arrow = Arrow(
            start=box.get_top() + UP * 0.9,
            end=box.get_top() + UP * 0.1,
            color=element.color,
            buff=0,
            stroke_width=6,
        )
        label = Text(element.label, font_size=24, color=element.color)
        label.next_to(arrow, UP, buff=0.05)

        mobject = VGroup(arrow, label)
        context.mobjects[element.id] = mobject
        context.pointer_index[element.id] = element.index
        return mobject
