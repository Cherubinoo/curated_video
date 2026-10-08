"""Component registry + build behavior. No Manim Scene/render needed here -
`SceneComponent.build()` only needs a RenderContext, so these stay fast."""
from __future__ import annotations

import pytest

from animation_engine.components.base import RenderContext
from animation_engine.components.registry import COMPONENT_REGISTRY, build_element, build_scene_elements
from app.schemas.specification.elements import ArrayElement, PointerElement


def test_registry_has_all_documented_element_types():
    expected = {
        "text", "title", "subtitle", "paragraph", "label", "rectangle", "circle",
        "line", "arrow", "array", "pointer", "code_block",
        "graph", "tree", "stack", "queue", "linked_list", "dp_table", "hash_map",
    }
    assert expected.issubset(COMPONENT_REGISTRY.keys())


def test_array_component_builds_one_cell_per_value():
    array = ArrayElement(id="arr1", values=[10, 20, 30])
    context = RenderContext(elements_by_id={"arr1": array})

    mobject = build_element(array, context)

    assert mobject is not None
    assert len(context.array_cells["arr1"]) == 3
    assert context.mobjects["arr1"] is mobject


def test_pointer_component_requires_array_built_first():
    array = ArrayElement(id="arr1", values=[1, 2, 3])
    pointer = PointerElement(id="ptr1", target="arr1", index=1)
    context = RenderContext(elements_by_id={"arr1": array, "ptr1": pointer})

    with pytest.raises(ValueError):
        build_element(pointer, context)  # array not built yet


def test_build_scene_elements_orders_pointer_after_array():
    array = ArrayElement(id="arr1", values=[1, 2, 3])
    pointer = PointerElement(id="ptr1", target="arr1", index=0)
    context = RenderContext(elements_by_id={"arr1": array, "ptr1": pointer})

    # Declared out of dependency order - the registry must still build the
    # array before the pointer that targets it.
    build_scene_elements([pointer, array], context)

    assert "arr1" in context.mobjects
    assert "ptr1" in context.mobjects
    assert context.pointer_index["ptr1"] == 0


def test_unimplemented_element_type_raises_clear_error():
    from app.schemas.specification.elements import StackElement

    stack = StackElement(id="s1", values=[1, 2])
    context = RenderContext(elements_by_id={"s1": stack})

    with pytest.raises(NotImplementedError, match="not implemented yet"):
        build_element(stack, context)
