"""Shared primitive types for the VideoSpecification DSL."""
from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")

# A subset of Manim's named colors we allow in addition to hex, so authors
# (human or future AI) don't have to memorize hex codes for common colors.
NAMED_COLORS = {
    "white", "black", "red", "green", "blue", "yellow", "orange", "purple",
    "pink", "teal", "gray", "grey", "gold", "maroon",
}


def validate_color(value: str) -> str:
    if value in NAMED_COLORS or HEX_COLOR_RE.match(value):
        return value
    raise ValueError(
        f"Invalid color {value!r}: must be a hex code like '#3B82F6' or one of {sorted(NAMED_COLORS)}"
    )


class DSLBaseModel(BaseModel):
    """Base for every DSL model: forbids unknown fields so malformed or
    unsupported objects are rejected outright, per the product spec."""

    model_config = ConfigDict(extra="forbid")


class Coordinate(DSLBaseModel):
    """An explicit point on the Manim canvas, in scene units (not pixels).

    Bounded to a safe-visible-area margin inside the actual 1920x1080/16:9
    frame edge (true edge is roughly x=+-7.1, y=+-4.0) so an out-of-frame
    coordinate is rejected outright by validation - caught by the same
    retry-with-feedback loop as any other invalid specification - instead
    of silently rendering a clipped/invisible element.
    """

    kind: Literal["coordinate"] = "coordinate"
    x: float = Field(ge=-6.5, le=6.5)
    y: float = Field(ge=-3.6, le=3.6)


class ElementAnchor(DSLBaseModel):
    """A point relative to an already-declared element, e.g. 'move this arrow
    to the top of array element 2'."""

    kind: Literal["element_anchor"] = "element_anchor"
    element_id: str
    anchor: Literal["center", "top", "bottom", "left", "right"] = "center"
    index: int | None = None  # optional sub-index, e.g. an array cell


PositionRef = Annotated[Union[Coordinate, ElementAnchor], Field(discriminator="kind")]
