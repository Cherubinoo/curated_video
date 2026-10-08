from __future__ import annotations

from manim import DOWN, UP, Text

from animation_engine.components.base import RenderContext, SceneComponent
from app.schemas.specification.elements import (
    LabelElement,
    ParagraphElement,
    SubtitleElement,
    TextElement,
    TitleElement,
)

# Empirically measured against the real renderer (Manim's default Pango
# Text, no LaTeX) - average rendered character width scales with font_size
# at roughly this rate. Used only to greedily word-wrap Paragraph content to
# its `line_width` - a real observed bug had ParagraphElement.line_width
# defined in the schema but silently ignored by this component, so any
# paragraph longer than a few words rendered as one unbroken line running
# off both edges of the frame regardless of the field's value.
_AVG_CHAR_WIDTH_PER_FONT_SIZE = 0.0075


def _wrap_paragraph(content: str, *, line_width: float, font_size: int) -> str:
    max_chars = max(1, int(line_width / (font_size * _AVG_CHAR_WIDTH_PER_FONT_SIZE)))
    lines: list[str] = []
    current = ""
    for word in content.split():
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


class TextComponent(SceneComponent):
    """Handles Text, Title, Subtitle, Paragraph and Label - all rendered as
    a positioned Manim `Text` mobject (Pango-based, no LaTeX dependency)."""

    def build(self, element, context: RenderContext) -> Text:
        content = getattr(element, "content", "")
        color = getattr(element, "color", "white")
        font_size = getattr(element, "font_size", 32)

        if isinstance(element, ParagraphElement):
            content = _wrap_paragraph(content, line_width=element.line_width, font_size=font_size)

        mobject = Text(content, font_size=font_size, color=color)

        position = getattr(element, "position", None)
        if position is not None:
            mobject.move_to(context.resolve_position(position))
        elif isinstance(element, TitleElement):
            mobject.to_edge(UP)
        elif isinstance(element, SubtitleElement):
            mobject.to_edge(UP).shift(DOWN * 1.0)
        elif isinstance(element, LabelElement) and element.target is not None:
            target_mobject = context.mobjects.get(element.target)
            if target_mobject is not None:
                mobject.next_to(target_mobject, UP, buff=0.25)

        context.mobjects[element.id] = mobject
        context.original_colors[element.id] = color
        return mobject
