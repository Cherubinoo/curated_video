"""Action definitions - the verbs of the DSL.

Actions reference one or more already-declared elements (`target`) and are
played in the order they appear within a scene (v1 keeps timing simple and
deterministic: sequential, not a general timeline). The union is
discriminated on `type`, so unknown action types are rejected by Pydantic.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, field_validator

from app.schemas.specification.common import DSLBaseModel, PositionRef, validate_color

Target = Union[str, list[str]]


class _BaseAction(DSLBaseModel):
    target: Target | None = None
    duration: float = Field(default=1.0, ge=0, le=60)
    wait_after: float = Field(default=0.0, ge=0, le=30)

    def target_ids(self) -> list[str]:
        if self.target is None:
            return []
        return [self.target] if isinstance(self.target, str) else list(self.target)


class CreateAction(_BaseAction):
    type: Literal["create"] = "create"


class ShowAction(_BaseAction):
    type: Literal["show"] = "show"


class HideAction(_BaseAction):
    type: Literal["hide"] = "hide"


class WriteAction(_BaseAction):
    type: Literal["write"] = "write"


class FadeInAction(_BaseAction):
    type: Literal["fade_in"] = "fade_in"


class FadeOutAction(_BaseAction):
    type: Literal["fade_out"] = "fade_out"


class MoveAction(_BaseAction):
    type: Literal["move"] = "move"
    to: PositionRef


class ShiftAction(_BaseAction):
    type: Literal["shift"] = "shift"
    dx: float = 0
    dy: float = 0


class ScaleAction(_BaseAction):
    type: Literal["scale"] = "scale"
    factor: float = Field(gt=0, le=10)


class RotateAction(_BaseAction):
    type: Literal["rotate"] = "rotate"
    angle_degrees: float = Field(ge=-360, le=360)


class HighlightAction(_BaseAction):
    type: Literal["highlight"] = "highlight"
    index: int | None = Field(default=None, ge=0)  # cell index, for Array/CodeBlock targets
    color: str = "yellow"

    _validate_color = field_validator("color")(validate_color)


class UnhighlightAction(_BaseAction):
    type: Literal["unhighlight"] = "unhighlight"
    index: int | None = Field(default=None, ge=0)


class TransformAction(_BaseAction):
    type: Literal["transform"] = "transform"
    into_element_id: str  # id of another declared element this one morphs into


class WaitAction(DSLBaseModel):
    type: Literal["wait"] = "wait"
    target: None = None
    duration: float = Field(default=1.0, ge=0, le=60)
    wait_after: float = Field(default=0.0, ge=0, le=30)

    def target_ids(self) -> list[str]:
        return []


class DrawArrowAction(_BaseAction):
    type: Literal["draw_arrow"] = "draw_arrow"


class MovePointerAction(_BaseAction):
    type: Literal["move_pointer"] = "move_pointer"
    index: int = Field(ge=0)


class SwapElementsAction(_BaseAction):
    type: Literal["swap_elements"] = "swap_elements"
    index_a: int = Field(ge=0)
    index_b: int = Field(ge=0)


class UpdateTextAction(_BaseAction):
    type: Literal["update_text"] = "update_text"
    new_text: str = Field(min_length=0, max_length=2000)


class HighlightCodeLineAction(_BaseAction):
    type: Literal["highlight_code_line"] = "highlight_code_line"
    line_number: int = Field(ge=0)  # 0-indexed
    color: str = "yellow"

    _validate_color = field_validator("color")(validate_color)


class CameraZoomAction(_BaseAction):
    type: Literal["camera_zoom"] = "camera_zoom"
    scale: float = Field(gt=0, le=10)


class CameraPanAction(_BaseAction):
    type: Literal["camera_pan"] = "camera_pan"
    to: PositionRef


ActionUnion = Annotated[
    Union[
        CreateAction,
        ShowAction,
        HideAction,
        WriteAction,
        FadeInAction,
        FadeOutAction,
        MoveAction,
        ShiftAction,
        ScaleAction,
        RotateAction,
        HighlightAction,
        UnhighlightAction,
        TransformAction,
        WaitAction,
        DrawArrowAction,
        MovePointerAction,
        SwapElementsAction,
        UpdateTextAction,
        HighlightCodeLineAction,
        CameraZoomAction,
        CameraPanAction,
    ],
    Field(discriminator="type"),
]
