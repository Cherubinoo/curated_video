"""Base types for the component layer: RenderContext (mutable state shared
across a scene's build) and the SceneComponent interface every component
implements. The animation engine never lets the DSL/AI touch Manim objects
directly - components are the only code that constructs Mobjects, and they
are fixed, reviewed Python, not generated at request time.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.schemas.specification.common import Coordinate, ElementAnchor, PositionRef
from app.schemas.specification.elements import ElementUnion


@dataclass
class RenderContext:
    """Per-scene mutable state built up as elements are constructed and
    mutated as actions run."""

    elements_by_id: dict[str, ElementUnion]
    mobjects: dict[str, Any] = field(default_factory=dict)  # element id -> top-level Mobject
    # Array element id -> list of (cell_group, value_text) Mobjects, one per cell.
    array_cells: dict[str, list[Any]] = field(default_factory=dict)
    # Code block element id -> list of (line_text, highlight_rect) per line.
    code_lines: dict[str, list[tuple[Any, Any]]] = field(default_factory=dict)
    # Pointer element id -> the array index it currently points at.
    pointer_index: dict[str, int] = field(default_factory=dict)
    # Array element id -> the ArrayElement spec it was built from (for bounds checks in actions).
    array_specs: dict[str, Any] = field(default_factory=dict)
    # Element id (or "array_id:index" for a cell) -> its color at build time, for `unhighlight`.
    original_colors: dict[str, str] = field(default_factory=dict)

    def resolve_position(self, pos: PositionRef | None) -> np.ndarray:
        if pos is None:
            return np.array([0.0, 0.0, 0.0])
        if isinstance(pos, Coordinate):
            return np.array([pos.x, pos.y, 0.0])
        if isinstance(pos, ElementAnchor):
            target = self.mobjects.get(pos.element_id)
            if target is None:
                return np.array([0.0, 0.0, 0.0])
            if pos.index is not None and pos.element_id in self.array_cells:
                cells = self.array_cells[pos.element_id]
                if 0 <= pos.index < len(cells):
                    target = cells[pos.index][0]
            edge_map = {
                "center": lambda m: m.get_center(),
                "top": lambda m: m.get_top(),
                "bottom": lambda m: m.get_bottom(),
                "left": lambda m: m.get_left(),
                "right": lambda m: m.get_right(),
            }
            return edge_map[pos.anchor](target)
        raise ValueError(f"Unsupported position reference: {pos!r}")


class SceneComponent(ABC):
    """One component builds one element's Mobject(s). `build_priority`
    controls construction order within a scene: components that reference
    other elements (pointers, arrows anchored to elements, labels) must
    build after the elements they depend on."""

    build_priority: int = 0

    @abstractmethod
    def build(self, element: ElementUnion, context: RenderContext):
        """Construct and return the Manim Mobject for `element`, registering
        it (and any sub-mobjects other components/actions will need) into
        `context`."""
        raise NotImplementedError


class UnimplementedComponent(SceneComponent):
    """Placeholder for DSA visualizations whose schema exists but whose
    renderer doesn't yet (Graph, Tree, Stack, Queue, LinkedList, DPTable,
    HashMap - see product spec Section 23). Fails loudly and specifically
    instead of silently producing nothing."""

    def __init__(self, element_type: str):
        self.element_type = element_type

    def build(self, element: ElementUnion, context: RenderContext):
        raise NotImplementedError(
            f"Element type '{self.element_type}' is schema-validated but its visual renderer "
            "is not implemented yet. This is a planned extension point - add a component in "
            "animation_engine/components/ and register it in animation_engine/components/registry.py."
        )
