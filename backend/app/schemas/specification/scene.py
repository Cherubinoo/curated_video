"""Scene model + the semantic (cross-reference) validation that Pydantic's
per-field validators can't express on their own: element id references,
index bounds, and duration sanity. This is what turns "syntactically valid
JSON" into "actually renderable JSON" per the product spec's requirement to
reject invalid indices, invalid pointer references, etc.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.schemas.specification.actions import (
    ActionUnion,
    HighlightAction,
    HighlightCodeLineAction,
    MovePointerAction,
    SwapElementsAction,
    TransformAction,
    UnhighlightAction,
)
from app.schemas.specification.common import DSLBaseModel, ElementAnchor
from app.schemas.specification.elements import (
    ArrayElement,
    ArrowElement,
    CodeBlockElement,
    ElementUnion,
    LabelElement,
    LineElement,
    PointerElement,
)

SceneType = Literal[
    "generic", "array", "pointer", "code", "graph", "tree", "stack", "queue", "dp_table", "hash_map"
]


class Scene(DSLBaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: SceneType = "generic"
    duration: float = Field(gt=0, le=120)
    background_color: str | None = None
    narration: str | None = Field(default=None, max_length=2000)
    elements: list[ElementUnion] = Field(default_factory=list)
    actions: list[ActionUnion] = Field(default_factory=list)

    # Populated by validation, not supplied by the author - non-fatal issues
    # (e.g. action durations that overrun the declared scene duration).
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_references(self) -> "Scene":
        elements_by_id: dict[str, ElementUnion] = {}
        for el in self.elements:
            if el.id in elements_by_id:
                raise ValueError(f"scene {self.id!r}: duplicate element id {el.id!r}")
            elements_by_id[el.id] = el

        def require_element(ref_id: str, context: str) -> ElementUnion:
            if ref_id not in elements_by_id:
                raise ValueError(
                    f"scene {self.id!r}: {context} references unknown element id {ref_id!r}"
                )
            return elements_by_id[ref_id]

        def check_position_ref(pos, context: str) -> None:
            if isinstance(pos, ElementAnchor):
                require_element(pos.element_id, context)

        # --- element-to-element references ---
        for el in self.elements:
            if isinstance(el, PointerElement):
                target = require_element(el.target, f"pointer {el.id!r}")
                if not isinstance(target, ArrayElement):
                    raise ValueError(
                        f"scene {self.id!r}: pointer {el.id!r} target {el.target!r} is not an array"
                    )
                if el.index >= len(target.values):
                    raise ValueError(
                        f"scene {self.id!r}: pointer {el.id!r} index {el.index} out of range "
                        f"for array {el.target!r} of length {len(target.values)}"
                    )
            elif isinstance(el, LabelElement) and el.target is not None:
                require_element(el.target, f"label {el.id!r}")
            elif isinstance(el, (ArrowElement, LineElement)):
                check_position_ref(el.start, f"{el.type} {el.id!r} start")
                check_position_ref(el.end, f"{el.type} {el.id!r} end")
            if hasattr(el, "position") and el.position is not None:
                check_position_ref(el.position, f"{el.type} {el.id!r} position")

        # --- action target + index-bound references ---
        total_duration = 0.0
        for i, action in enumerate(self.actions):
            context = f"action[{i}] ({action.type})"
            total_duration += action.duration + action.wait_after

            target_ids = action.target_ids()
            targets = [require_element(t, context) for t in target_ids]

            if isinstance(action, (HighlightAction, UnhighlightAction)) and action.index is not None:
                for t in targets:
                    if isinstance(t, ArrayElement) and action.index >= len(t.values):
                        raise ValueError(
                            f"scene {self.id!r}: {context} index {action.index} out of range "
                            f"for array {t.id!r} of length {len(t.values)}"
                        )
            elif isinstance(action, MovePointerAction):
                for t in targets:
                    if not isinstance(t, PointerElement):
                        raise ValueError(
                            f"scene {self.id!r}: {context} target {t.id!r} is not a pointer"
                        )
                    array_el = elements_by_id.get(t.target)
                    if isinstance(array_el, ArrayElement) and action.index >= len(array_el.values):
                        raise ValueError(
                            f"scene {self.id!r}: {context} index {action.index} out of range "
                            f"for array {array_el.id!r} of length {len(array_el.values)}"
                        )
            elif isinstance(action, SwapElementsAction):
                for t in targets:
                    if isinstance(t, ArrayElement):
                        for idx in (action.index_a, action.index_b):
                            if idx >= len(t.values):
                                raise ValueError(
                                    f"scene {self.id!r}: {context} index {idx} out of range "
                                    f"for array {t.id!r} of length {len(t.values)}"
                                )
            elif isinstance(action, HighlightCodeLineAction):
                for t in targets:
                    if not isinstance(t, CodeBlockElement):
                        raise ValueError(
                            f"scene {self.id!r}: {context} target {t.id!r} is not a code_block"
                        )
                    if action.line_number >= len(t.lines):
                        raise ValueError(
                            f"scene {self.id!r}: {context} line_number {action.line_number} out of "
                            f"range for code_block {t.id!r} with {len(t.lines)} lines"
                        )
            elif isinstance(action, TransformAction):
                require_element(action.into_element_id, context)

        if total_duration > self.duration + 0.01:
            self.warnings.append(
                f"scene {self.id!r}: total action duration ({total_duration:.2f}s) exceeds the "
                f"declared scene duration ({self.duration:.2f}s)"
            )

        return self
