"""Action executors, exercised through `execute_action()` against a fake
Manim scene stub - no real rendering, so these stay fast."""
from __future__ import annotations

from animation_engine.actions.registry import execute_action
from animation_engine.components.base import RenderContext
from animation_engine.components.registry import build_scene_elements
from app.schemas.specification.actions import (
    HighlightAction,
    HighlightCodeLineAction,
    MovePointerAction,
    UnhighlightAction,
    WaitAction,
)
from app.schemas.specification.elements import ArrayElement, CodeBlockElement, PointerElement


class FakeScene:
    """Records what would have been played/waited, without touching Manim's
    real renderer."""

    def __init__(self):
        self.played: list[tuple] = []
        self.waited: list[float] = []

    def play(self, *animations, run_time=None):
        self.played.append((animations, run_time))

    def wait(self, duration=1.0):
        self.waited.append(duration)

    def add(self, *mobjects):
        pass

    def remove(self, *mobjects):
        pass


def _array_context():
    array = ArrayElement(id="arr1", values=[1, 2, 3, 4, 5])
    context = RenderContext(elements_by_id={"arr1": array})
    build_scene_elements([array], context)
    return context


def test_highlight_action_recolors_the_target_cell():
    context = _array_context()
    scene = FakeScene()
    action = HighlightAction(target="arr1", index=2, color="green", duration=0.5)

    execute_action(scene, context, action)

    assert len(scene.played) == 1
    animations, run_time = scene.played[0]
    assert len(animations) == 2  # box + value text
    assert run_time == 0.5


def test_unhighlight_restores_original_color():
    context = _array_context()
    scene = FakeScene()
    execute_action(scene, context, HighlightAction(target="arr1", index=0, color="red", duration=0.1))
    execute_action(scene, context, UnhighlightAction(target="arr1", index=0, duration=0.1))
    assert len(scene.played) == 2


def test_move_pointer_updates_context_index():
    array = ArrayElement(id="arr1", values=[1, 2, 3, 4, 5])
    pointer = PointerElement(id="ptr1", target="arr1", index=0)
    context = RenderContext(elements_by_id={"arr1": array, "ptr1": pointer})
    build_scene_elements([array, pointer], context)

    scene = FakeScene()
    execute_action(scene, context, MovePointerAction(target="ptr1", index=3, duration=1.0))

    assert context.pointer_index["ptr1"] == 3
    assert len(scene.played) == 1


def test_highlight_code_line_targets_correct_line():
    code = CodeBlockElement(id="code1", lines=["def f():", "    return 1", "    pass"])
    context = RenderContext(elements_by_id={"code1": code})
    build_scene_elements([code], context)

    scene = FakeScene()
    execute_action(scene, context, HighlightCodeLineAction(target="code1", line_number=1, duration=0.4))

    assert len(scene.played) == 1
    animations, run_time = scene.played[0]
    assert len(animations) == 1
    assert run_time == 0.4


def test_wait_action_calls_scene_wait_not_play():
    context = _array_context()
    scene = FakeScene()
    execute_action(scene, context, WaitAction(duration=2.0))

    assert scene.played == []
    assert scene.waited == [2.0]


def test_action_wait_after_adds_an_additional_wait():
    context = _array_context()
    scene = FakeScene()
    execute_action(scene, context, HighlightAction(target="arr1", index=0, duration=0.5, wait_after=1.5))

    assert scene.waited == [1.5]
