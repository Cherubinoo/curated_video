from __future__ import annotations

from manim import DOWN, RIGHT, Rectangle, Text, VGroup

from animation_engine.components.base import RenderContext, SceneComponent


class ArrayComponent(SceneComponent):
    """Builds a row of boxes for an ArrayElement. Individual cells are not
    separate top-level DSL elements (see elements.py docstring); instead
    each cell's (rectangle, value_text) pair is registered into
    `context.array_cells[element.id]` so Pointer/Highlight/Swap actions can
    address a cell by index."""

    def build(self, element, context: RenderContext) -> VGroup:
        cells = []
        for i, value in enumerate(element.values):
            box = Rectangle(width=element.cell_size, height=element.cell_size, color=element.color)
            value_text = Text(str(value), font_size=32, color=element.color)
            value_text.move_to(box.get_center())
            cell = VGroup(box, value_text)

            if element.labels is not None:
                label = Text(element.labels[i], font_size=20, color="gray")
                label.next_to(box, DOWN, buff=0.15)
                cell.add(label)

            context.original_colors[f"{element.id}:{i}"] = element.color
            cells.append(cell)

        array_group = VGroup(*cells).arrange(RIGHT, buff=0.15)
        if element.position is not None:
            array_group.move_to(context.resolve_position(element.position))

        context.mobjects[element.id] = array_group
        context.array_cells[element.id] = [(cell[0], cell[1]) for cell in cells]
        context.array_specs[element.id] = element
        return array_group
