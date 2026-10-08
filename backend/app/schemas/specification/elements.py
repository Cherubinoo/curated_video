"""Scene element definitions - the nouns of the DSL.

Every element has a stable `id` (unique within its scene) that actions refer
to as `target`. The union is discriminated on `type`, so an unknown element
type is rejected by Pydantic itself (no need for a manual check).

Elements marked "not yet rendered" are schema-complete extension points for
future DSA topics (graphs, trees, heaps, DP tables, ...): the shape of the
data is locked down now so the API/validation/storage layers never need to
change, but `animation_engine.components` does not implement their visuals
yet - see `animation_engine/components/unimplemented.py`.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from app.schemas.specification.common import DSLBaseModel, PositionRef, validate_color

ElementId = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_\-]+$")]


class _PositionedElement(DSLBaseModel):
    id: ElementId
    position: PositionRef | None = None


# ---------------------------------------------------------------------------
# Text family
# ---------------------------------------------------------------------------

class TextElement(_PositionedElement):
    type: Literal["text"] = "text"
    content: str = Field(min_length=1, max_length=2000)
    font_size: int = Field(default=36, ge=8, le=200)
    color: str = "white"

    _validate_color = field_validator("color")(validate_color)


class TitleElement(_PositionedElement):
    type: Literal["title"] = "title"
    content: str = Field(min_length=1, max_length=200)
    font_size: int = Field(default=56, ge=8, le=200)
    color: str = "white"

    _validate_color = field_validator("color")(validate_color)


class SubtitleElement(_PositionedElement):
    type: Literal["subtitle"] = "subtitle"
    content: str = Field(min_length=1, max_length=300)
    font_size: int = Field(default=32, ge=8, le=200)
    color: str = "gray"

    _validate_color = field_validator("color")(validate_color)


class ParagraphElement(_PositionedElement):
    type: Literal["paragraph"] = "paragraph"
    content: str = Field(min_length=1, max_length=2000)
    font_size: int = Field(default=28, ge=8, le=200)
    color: str = "white"
    line_width: float = Field(default=10.0, gt=0)

    _validate_color = field_validator("color")(validate_color)

    @model_validator(mode="after")
    def _fits_on_screen(self) -> "ParagraphElement":
        """A real observed bug: `line_width` was defined here but silently
        ignored by the renderer, so any paragraph longer than a few words
        rendered as one unbroken line running off both edges of the frame.
        Wrapping is now implemented (see animation_engine/components/
        text.py's `_wrap_paragraph`, calibrated against the real renderer),
        but a long `content` at a narrow `line_width` can still wrap into
        enough lines to overflow its layout zone vertically - this estimates
        that and rejects it the same way an oversized code_block is
        rejected, using the same calibration approach (line height scales
        with font_size; ~0.0135*font_size per line, live-measured)."""
        max_chars_per_line = max(1, int(self.line_width / (self.font_size * 0.0075)))
        est_lines = max(1, -(-len(self.content) // max_chars_per_line))  # ceiling division
        est_height = est_lines * self.font_size * 0.0135
        if est_height > 2.8:
            raise ValueError(
                f"paragraph '{self.id}' wraps to an estimated ~{est_lines} lines "
                f"(~{est_height:.1f} units tall) at its current content length/line_width/font_size "
                "- max ~2.8 units: shorten the content, increase line_width, and/or use a smaller "
                "font_size"
            )
        return self


class LabelElement(_PositionedElement):
    type: Literal["label"] = "label"
    content: str = Field(min_length=1, max_length=200)
    target: str | None = None  # element id this label annotates
    font_size: int = Field(default=24, ge=8, le=200)
    color: str = "white"

    _validate_color = field_validator("color")(validate_color)


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

class RectangleElement(_PositionedElement):
    type: Literal["rectangle"] = "rectangle"
    width: float = Field(default=1.5, gt=0)
    height: float = Field(default=1.0, gt=0)
    color: str = "white"
    fill_opacity: float = Field(default=0.0, ge=0, le=1)

    _validate_color = field_validator("color")(validate_color)


class CircleElement(_PositionedElement):
    type: Literal["circle"] = "circle"
    radius: float = Field(default=0.5, gt=0)
    color: str = "white"
    fill_opacity: float = Field(default=0.0, ge=0, le=1)

    _validate_color = field_validator("color")(validate_color)


class LineElement(DSLBaseModel):
    type: Literal["line"] = "line"
    id: ElementId
    start: PositionRef
    end: PositionRef
    color: str = "white"

    _validate_color = field_validator("color")(validate_color)


class ArrowElement(DSLBaseModel):
    type: Literal["arrow"] = "arrow"
    id: ElementId
    start: PositionRef
    end: PositionRef
    color: str = "yellow"
    label: str | None = None

    _validate_color = field_validator("color")(validate_color)


# ---------------------------------------------------------------------------
# Core DSA primitives (fully implemented)
# ---------------------------------------------------------------------------

class ArrayElement(_PositionedElement):
    """An array/list visualized as a row of boxes. Individual cells are not
    declared as separate top-level elements; actions that touch one cell
    (highlight, swap_elements, ...) reference this array's `id` plus an
    `index` parameter instead."""

    type: Literal["array"] = "array"
    values: list[int | float | str] = Field(min_length=1, max_length=64)
    labels: list[str] | None = None  # optional per-cell label, same length as values
    cell_size: float = Field(default=1.0, gt=0)
    color: str = "white"

    _validate_color = field_validator("color")(validate_color)

    @field_validator("labels")
    @classmethod
    def _labels_len_matches(cls, v, info):
        values = info.data.get("values")
        if v is not None and values is not None and len(v) != len(values):
            raise ValueError("labels must be the same length as values")
        return v


class PointerElement(DSLBaseModel):
    type: Literal["pointer"] = "pointer"
    id: ElementId
    target: str  # id of the ArrayElement this pointer points into
    index: int = Field(ge=0)
    label: str = "ptr"
    color: str = "yellow"

    _validate_color = field_validator("color")(validate_color)


class CodeBlockElement(_PositionedElement):
    type: Literal["code_block"] = "code_block"
    language: str = "python"
    lines: list[str] = Field(min_length=1, max_length=200)
    font_size: int = Field(default=28, ge=8, le=72)

    @field_validator("lines")
    @classmethod
    def _no_overlong_lines(cls, v: list[str]) -> list[str]:
        for line in v:
            if len(line) > 200:
                raise ValueError("code_block lines must be <= 200 characters")
        return v

    @model_validator(mode="after")
    def _fits_on_screen(self) -> "CodeBlockElement":
        """A real observed overlap bug: nothing capped total line count, so
        an 11-line block at the default font_size rendered ~5.5 units tall -
        nearly the whole frame - guaranteeing it collided with anything else
        on screen regardless of position. Height/width here are calibrated
        against the actual Manim renderer (DejaVu Sans Mono, 0.18 buff
        between lines - see animation_engine/components/code_block.py),
        not guessed: height(lines, font_size) = lines * (0.0139*font_size +
        0.18) - 0.18; width scales as longest_line_chars * font_size *
        0.008. Caps leave real margin within the layout zones described in
        dsl_reference.py so a code_block can never overrun its neighbors."""
        n = len(self.lines)
        est_height = n * (0.0139 * self.font_size + 0.18) - 0.18
        if est_height > 2.8:
            raise ValueError(
                f"code_block '{self.id}' is too tall to fit on screen without overlapping other "
                f"elements (~{est_height:.1f} units at {n} lines and font_size {self.font_size}, "
                "max ~2.8 units) - use fewer lines and/or a smaller font_size, or split the code "
                "across two scenes"
            )
        longest = max((len(line) for line in self.lines), default=0)
        est_width = longest * self.font_size * 0.008
        if est_width > 6.5:
            raise ValueError(
                f"code_block '{self.id}' is too wide to fit on screen without overlapping other "
                f"elements (~{est_width:.1f} units at {longest} characters on its longest line and "
                f"font_size {self.font_size}, max ~6.5 units) - shorten the longest line and/or use "
                "a smaller font_size"
            )
        return self


# ---------------------------------------------------------------------------
# Future DSA visualizations - schema-complete, rendering not implemented yet
# ---------------------------------------------------------------------------

class GraphNodeDef(DSLBaseModel):
    id: ElementId
    label: str = ""
    position: PositionRef | None = None


class GraphEdgeDef(DSLBaseModel):
    source: str
    target: str
    weight: float | None = None
    directed: bool = False


class GraphElement(DSLBaseModel):
    type: Literal["graph"] = "graph"
    id: ElementId
    nodes: list[GraphNodeDef] = Field(min_length=1)
    edges: list[GraphEdgeDef] = Field(default_factory=list)


class TreeNodeDef(DSLBaseModel):
    id: ElementId
    label: str = ""
    parent_id: str | None = None


class TreeElement(DSLBaseModel):
    type: Literal["tree"] = "tree"
    id: ElementId
    nodes: list[TreeNodeDef] = Field(min_length=1)


class StackElement(_PositionedElement):
    type: Literal["stack"] = "stack"
    values: list[int | float | str] = Field(default_factory=list)


class QueueElement(_PositionedElement):
    type: Literal["queue"] = "queue"
    values: list[int | float | str] = Field(default_factory=list)


class LinkedListElement(_PositionedElement):
    type: Literal["linked_list"] = "linked_list"
    values: list[int | float | str] = Field(min_length=1)


class DPTableElement(_PositionedElement):
    type: Literal["dp_table"] = "dp_table"
    rows: int = Field(gt=0, le=20)
    cols: int = Field(gt=0, le=20)
    values: list[list[int | float | str | None]] | None = None
    row_labels: list[str] | None = None
    col_labels: list[str] | None = None


class HashMapEntryDef(DSLBaseModel):
    key: str
    value: str


class HashMapElement(_PositionedElement):
    type: Literal["hash_map"] = "hash_map"
    entries: list[HashMapEntryDef] = Field(default_factory=list)


ElementUnion = Annotated[
    Union[
        TextElement,
        TitleElement,
        SubtitleElement,
        ParagraphElement,
        LabelElement,
        RectangleElement,
        CircleElement,
        LineElement,
        ArrowElement,
        ArrayElement,
        PointerElement,
        CodeBlockElement,
        GraphElement,
        TreeElement,
        StackElement,
        QueueElement,
        LinkedListElement,
        DPTableElement,
        HashMapElement,
    ],
    Field(discriminator="type"),
]

# Element types whose visual rendering is not implemented yet (Phase-23
# extension points). Kept in one place so the component registry and error
# messages stay consistent.
UNIMPLEMENTED_ELEMENT_TYPES = {
    "graph",
    "tree",
    "stack",
    "queue",
    "linked_list",
    "dp_table",
    "hash_map",
}
