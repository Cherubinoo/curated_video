"""Validates the DSL rejects everything the product spec says it must:
unknown action/element types, invalid indices, invalid pointer references,
invalid durations, malformed/unsupported data."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from animation_engine.validators.specification_validator import validate_specification
from app.services.ai.demo_specification import build_demo_specification

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def valid_spec() -> dict:
    return build_demo_specification()


def _scene_by_id(spec: dict, scene_id: str) -> dict:
    return next(s for s in spec["scenes"] if s["id"] == scene_id)


def _element_by_id(scene: dict, element_id: str) -> dict:
    return next(e for e in scene["elements"] if e["id"] == element_id)


def test_valid_specification_passes(valid_spec):
    result = validate_specification(valid_spec)
    assert result.is_valid
    assert result.specification is not None
    assert result.errors == []


@pytest.mark.parametrize(
    "x,y",
    [
        (10.0, 0.0),      # off the right edge
        (-10.0, 0.0),     # off the left edge
        (0.0, 10.0),      # off the top edge
        (0.0, -10.0),     # off the bottom edge
    ],
)
def test_out_of_frame_coordinates_are_rejected(valid_spec, x, y):
    # Regression check for real generated videos that had text/boxes
    # overflowing the visible frame - coordinates outside the safe-visible
    # area must fail validation outright, not silently render off-screen.
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    _element_by_id(main_scene, "arr1")["position"] = {"kind": "coordinate", "x": x, "y": y}
    result = validate_specification(spec)
    assert not result.is_valid


def test_in_frame_coordinates_at_the_bounds_are_accepted(valid_spec):
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    _element_by_id(main_scene, "arr1")["position"] = {"kind": "coordinate", "x": 6.5, "y": -3.6}
    result = validate_specification(spec)
    assert result.is_valid, result.errors


def test_oversized_code_block_is_rejected(valid_spec):
    # Regression check for a real observed overlap bug: nothing capped line
    # count, so an 11-line block at font_size 24 rendered ~5.5 units tall -
    # nearly the whole frame - and overlapped every other element on screen
    # regardless of position.
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    code_block = _element_by_id(main_scene, "code1")
    code_block["font_size"] = 24
    code_block["lines"] = [f"line_{i} = {i}" for i in range(11)]
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("too tall" in e.lower() for e in result.errors)


def test_max_height_code_block_at_default_font_size_is_accepted(valid_spec):
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    code_block = _element_by_id(main_scene, "code1")
    code_block["font_size"] = 24
    code_block["lines"] = [f"x{i} = {i}" for i in range(5)]  # at the documented 5-line cap
    result = validate_specification(spec)
    assert result.is_valid, result.errors


def test_too_wide_code_block_line_is_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    code_block = _element_by_id(main_scene, "code1")
    code_block["font_size"] = 24
    code_block["lines"] = ["x" * 60]  # one line, but far past the ~33-char width cap at font_size 24
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("too wide" in e.lower() for e in result.errors)


def test_oversized_paragraph_is_rejected(valid_spec):
    # Regression check for a real observed overlap/overflow bug: a
    # ParagraphElement's `line_width` was defined in the schema but
    # silently ignored by the renderer, so any long paragraph rendered as
    # one unbroken line running off both edges of the frame. Wrapping is
    # now implemented, but a long-enough paragraph can still wrap into
    # enough lines to overflow its zone vertically - that must be rejected.
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    main_scene["elements"].append(
        {
            "type": "paragraph",
            "id": "para1",
            "content": "word " * 200,
            "font_size": 26,
            "line_width": 9.0,
            "position": {"kind": "coordinate", "x": 0, "y": -1.5},
        }
    )
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("para1" in e and "lines" in e for e in result.errors)


def test_reasonably_sized_paragraph_is_accepted(valid_spec):
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    main_scene["elements"].append(
        {
            "type": "paragraph",
            "id": "para1",
            "content": "Two pointers efficiently finds a pair sum in a sorted array.",
            "font_size": 26,
            "line_width": 9.0,
            "position": {"kind": "coordinate", "x": 0, "y": -1.5},
        }
    )
    result = validate_specification(spec)
    assert result.is_valid, result.errors


def test_polly_is_an_accepted_voice_provider():
    # Regression check: this exact combination (real narration + Polly)
    # failed validation once before "polly" was added to the allowed set.
    spec = build_demo_specification(narration="Some narration text.", voice_provider="polly")
    result = validate_specification(spec)
    assert result.is_valid, result.errors
    assert result.specification.audio.voice_provider == "polly"


def test_unknown_action_type_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["actions"].append({"type": "teleport", "target": "arr1"})
    result = validate_specification(spec)
    assert not result.is_valid
    assert result.errors


def test_unknown_element_type_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["elements"].append({"type": "hologram", "id": "h1"})
    result = validate_specification(spec)
    assert not result.is_valid


def test_action_referencing_unknown_element_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["actions"].append({"type": "highlight", "target": "does_not_exist"})
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("unknown element id" in e for e in result.errors)


def test_pointer_out_of_range_index_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    # arr1 (in scene_main) has 7 elements (indices 0-6)
    main_scene = _scene_by_id(spec, "scene_main")
    _element_by_id(main_scene, "left_ptr")["index"] = 99
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("out of range" in e for e in result.errors)


def test_move_pointer_out_of_range_index_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    main_scene = _scene_by_id(spec, "scene_main")
    moved = False
    for action in main_scene["actions"]:
        if action["type"] == "move_pointer":
            action["index"] = 999
            moved = True
    assert moved, "fixture no longer has a move_pointer action to corrupt"
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("out of range" in e for e in result.errors)


def test_negative_duration_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["actions"][0]["duration"] = -5
    result = validate_specification(spec)
    assert not result.is_valid


def test_zero_scene_duration_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["duration"] = 0
    result = validate_specification(spec)
    assert not result.is_valid


def test_unknown_field_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["elements"][1]["totally_made_up_field"] = 123
    result = validate_specification(spec)
    assert not result.is_valid


def test_duplicate_element_id_rejected(valid_spec):
    spec = copy.deepcopy(valid_spec)
    dup = copy.deepcopy(spec["scenes"][0]["elements"][0])
    spec["scenes"][0]["elements"].append(dup)
    result = validate_specification(spec)
    assert not result.is_valid
    assert any("duplicate element id" in e for e in result.errors)


def test_not_a_dict_rejected():
    result = validate_specification(["not", "a", "dict"])  # type: ignore[arg-type]
    assert not result.is_valid


def test_bundled_fixture_json_on_disk_is_valid():
    """The first end-to-end test's fixture file (Section 20) must stay in
    sync with `build_demo_specification()` - both describe the same demo."""
    raw = json.loads((FIXTURES_DIR / "simple_array_pointer_demo.json").read_text(encoding="utf-8"))
    result = validate_specification(raw)
    assert result.is_valid, result.errors


def test_overrunning_action_durations_produce_a_warning_not_a_failure(valid_spec):
    spec = copy.deepcopy(valid_spec)
    spec["scenes"][0]["duration"] = 0.01
    for action in spec["scenes"][0]["actions"]:
        action["duration"] = max(action.get("duration", 1.0), 0.5)
    # duration bound on Scene is >0, so 0.01 still parses; the overrun check
    # is a soft warning, not a hard validation failure.
    result = validate_specification(spec)
    assert result.is_valid
    assert result.warnings
