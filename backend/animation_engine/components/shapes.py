from __future__ import annotations

from manim import Circle, Line, Rectangle

from animation_engine.components.base import RenderContext, SceneComponent


class RectangleComponent(SceneComponent):
    def build(self, element, context: RenderContext) -> Rectangle:
        mobject = Rectangle(
            width=element.width, height=element.height, color=element.color,
            fill_opacity=element.fill_opacity,
        )
        if element.position is not None:
            mobject.move_to(context.resolve_position(element.position))
        context.mobjects[element.id] = mobject
        context.original_colors[element.id] = element.color
        return mobject


class CircleComponent(SceneComponent):
    def build(self, element, context: RenderContext) -> Circle:
        mobject = Circle(radius=element.radius, color=element.color, fill_opacity=element.fill_opacity)
        if element.position is not None:
            mobject.move_to(context.resolve_position(element.position))
        context.mobjects[element.id] = mobject
        context.original_colors[element.id] = element.color
        return mobject


class LineComponent(SceneComponent):
    """Handles the plain Line element. Depends on any elements referenced by
    ElementAnchor endpoints, so it must build after those."""

    build_priority = 2

    def build(self, element, context: RenderContext) -> Line:
        start = context.resolve_position(element.start)
        end = context.resolve_position(element.end)
        mobject = Line(start=start, end=end, color=element.color)
        context.mobjects[element.id] = mobject
        return mobject
