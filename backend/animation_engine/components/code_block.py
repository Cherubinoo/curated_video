from __future__ import annotations

from manim import DOWN, LEFT, SurroundingRectangle, Text, VGroup

from animation_engine.components.base import RenderContext, SceneComponent


class CodeBlockComponent(SceneComponent):
    """Renders each source line as monospace Text stacked vertically, with a
    per-line, initially-invisible highlight rectangle behind it that
    `highlight_code_line` fades in/recolors."""

    def build(self, element, context: RenderContext) -> VGroup:
        line_mobjects = [
            Text(
                line if line.strip() else " ",
                font="DejaVu Sans Mono",
                font_size=element.font_size,
                color="white",
            )
            for line in element.lines
        ]
        code_group = VGroup(*line_mobjects).arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        if element.position is not None:
            code_group.move_to(context.resolve_position(element.position))

        highlight_rects = [
            SurroundingRectangle(text, color="yellow", buff=0.08, fill_opacity=0, stroke_opacity=0)
            for text in line_mobjects
        ]

        mobject = VGroup(*highlight_rects, code_group)
        context.mobjects[element.id] = mobject
        context.code_lines[element.id] = list(zip(line_mobjects, highlight_rects))
        return mobject
