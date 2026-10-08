from __future__ import annotations

from manim import UP, Arrow, Text, VGroup

from animation_engine.components.base import RenderContext, SceneComponent


class ArrowComponent(SceneComponent):
    """Depends on any elements referenced by ElementAnchor endpoints, so it
    must build after ordinary elements (arrays, shapes, text)."""

    build_priority = 2

    def build(self, element, context: RenderContext):
        start = context.resolve_position(element.start)
        end = context.resolve_position(element.end)
        arrow = Arrow(start=start, end=end, color=element.color, buff=0.1)

        if element.label:
            label = Text(element.label, font_size=24, color=element.color)
            label.next_to(arrow, UP, buff=0.1)
            mobject = VGroup(arrow, label)
        else:
            mobject = arrow

        context.mobjects[element.id] = mobject
        # Keep a handle to the bare arrow for draw_arrow's Create() animation.
        context.mobjects[f"{element.id}::arrow"] = arrow
        return mobject
