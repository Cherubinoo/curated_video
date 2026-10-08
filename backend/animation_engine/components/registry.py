"""Element-type -> component registry. This is the extension point for
adding new DSA visualizations later: implement a SceneComponent subclass and
add one line here - nothing else in the pipeline (API, validation, worker)
needs to change.
"""
from __future__ import annotations

from animation_engine.components.array import ArrayComponent
from animation_engine.components.arrow import ArrowComponent
from animation_engine.components.base import RenderContext, SceneComponent, UnimplementedComponent
from animation_engine.components.code_block import CodeBlockComponent
from animation_engine.components.pointer import PointerComponent
from animation_engine.components.shapes import CircleComponent, LineComponent, RectangleComponent
from animation_engine.components.text import TextComponent
from app.schemas.specification.elements import UNIMPLEMENTED_ELEMENT_TYPES, ElementUnion

_text_component = TextComponent()
_label_component = TextComponent()
_label_component.build_priority = 2  # labels may `next_to` a target element

COMPONENT_REGISTRY: dict[str, SceneComponent] = {
    "text": _text_component,
    "title": _text_component,
    "subtitle": _text_component,
    "paragraph": _text_component,
    "label": _label_component,
    "rectangle": RectangleComponent(),
    "circle": CircleComponent(),
    "line": LineComponent(),
    "arrow": ArrowComponent(),
    "array": ArrayComponent(),
    "pointer": PointerComponent(),
    "code_block": CodeBlockComponent(),
}

for _type in UNIMPLEMENTED_ELEMENT_TYPES:
    COMPONENT_REGISTRY[_type] = UnimplementedComponent(_type)


def build_element(element: ElementUnion, context: RenderContext):
    component = COMPONENT_REGISTRY.get(element.type)
    if component is None:
        raise ValueError(f"No component registered for element type {element.type!r}")
    return component.build(element, context)


def build_scene_elements(elements: list[ElementUnion], context: RenderContext) -> None:
    """Builds every element in dependency order (lower build_priority
    first), preserving declaration order within the same priority."""

    def priority(el: ElementUnion) -> int:
        component = COMPONENT_REGISTRY.get(el.type)
        return component.build_priority if component is not None else 0

    for element in sorted(elements, key=priority):
        build_element(element, context)
