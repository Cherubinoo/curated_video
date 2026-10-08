"""The one bundled, hand-authored VideoSpecification used by the platform
foundation demo. This is deliberately NOT any real DSA lesson (not Two
Pointers, not anything else) - it exists purely to exercise every layer of
the pipeline end to end (product spec Section 20/21's first end-to-end
test) while actually showing off what the animation engine can do: a title
card, an array, two pointers converging with real movement, a code panel
with synced line-highlighting, a payoff moment, a camera flourish, and an
outro - three scenes with a beginning/middle/end rather than one flat
tableau.

`PlaceholderSpecGenerator` (see specification_generator.py) returns this
today because no real AI generator produces full scene/action data yet;
`backend/tests/` uses the same builder so the demo and the tests never
drift apart.
"""
from __future__ import annotations

# The array driving the "main" scene - kept module-level so every action
# below that references an index can be sanity-checked against its length.
_ARRAY_VALUES = [4, 1, 9, 3, 7, 2, 8]
_LEFT_START, _RIGHT_START, _MEET_AT = 0, len(_ARRAY_VALUES) - 1, len(_ARRAY_VALUES) // 2


def build_demo_specification(
    title: str = "DSA Video Studio - Platform Demo",
    topic: str = "platform-demo",
    duration_target: int = 20,
    narration: str | None = None,
    voice_provider: str = "none",
) -> dict:
    """`narration`/`voice_provider` let a VideoSpecificationGenerator (e.g.
    BedrockSpecificationGenerator) slot in real narrative text without
    touching the animation shell itself - see that module's docstring for
    why the AI is only ever allowed to supply text, never structured scene
    data. The narration is attached to the "main" scene; the top-level
    `audio.narration_script` is what actually gets voiced."""
    on_screen_title = title[:60] if len(title) > 60 else title

    return {
        "version": "1.0",
        "metadata": {
            "title": title,
            "topic": topic,
            "duration_target": duration_target,
            "difficulty": "beginner",
        },
        "settings": {"width": 1920, "height": 1080, "fps": 30, "background_color": "#0e1116"},
        "scenes": [
            _intro_scene(on_screen_title),
            _main_scene(narration),
            _outro_scene(),
        ],
        "assets": [],
        "audio": {
            "enabled": narration is not None,
            "narration_script": narration,
            "voice_provider": voice_provider,
        },
        "subtitles": {"enabled": False, "provider": "none"},
    }


def _intro_scene(on_screen_title: str) -> dict:
    return {
        "id": "scene_intro",
        "type": "generic",
        "duration": 4.5,
        "narration": None,
        "elements": [
            {"type": "title", "id": "intro_title", "content": on_screen_title, "font_size": 52, "color": "white"},
            {
                "type": "subtitle",
                "id": "intro_subtitle",
                "content": "A look at what this platform can animate",
                "font_size": 30,
                "color": "gray",
            },
        ],
        "actions": [
            {"type": "write", "target": "intro_title", "duration": 1.2},
            {"type": "write", "target": "intro_subtitle", "duration": 1.0, "wait_after": 0.6},
            {"type": "fade_out", "target": ["intro_title", "intro_subtitle"], "duration": 0.8},
        ],
    }


def _main_scene(narration: str | None) -> dict:
    return {
        "id": "scene_main",
        "type": "array",
        "duration": 16,
        "narration": narration,
        "elements": [
            {
                "type": "text",
                "id": "caption1",
                "content": "Watch two pointers scan the array",
                "font_size": 36,
                "color": "white",
                "position": {"kind": "coordinate", "x": 0, "y": 3.0},
            },
            {
                "type": "array",
                "id": "arr1",
                "values": _ARRAY_VALUES,
                "cell_size": 1.0,
                "color": "white",
                "position": {"kind": "coordinate", "x": 0, "y": 1.6},
            },
            {
                "type": "code_block",
                "id": "code1",
                "language": "text",
                "lines": [
                    "left, right = 0, len(arr) - 1",
                    "while left < right:",
                    "    step(left, right)",
                    "    left += 1",
                    "    right -= 1",
                ],
                "font_size": 24,
                "position": {"kind": "coordinate", "x": 0, "y": -1.8},
            },
            {
                "type": "pointer",
                "id": "left_ptr",
                "target": "arr1",
                "index": _LEFT_START,
                "label": "L",
                "color": "blue",
            },
            {
                "type": "pointer",
                "id": "right_ptr",
                "target": "arr1",
                "index": _RIGHT_START,
                "label": "R",
                "color": "orange",
            },
            {
                "type": "text",
                "id": "result_text",
                "content": "Pointers meet in the middle!",
                "font_size": 32,
                "color": "gold",
                "position": {"kind": "coordinate", "x": 0, "y": -3.3},
            },
        ],
        "actions": [
            {"type": "write", "target": "caption1", "duration": 1.0},
            {"type": "create", "target": ["arr1"], "duration": 1.0},
            {"type": "create", "target": ["code1"], "duration": 1.0},
            {"type": "create", "target": ["left_ptr"], "duration": 0.4},
            {"type": "create", "target": ["right_ptr"], "duration": 0.4},
            {"type": "highlight_code_line", "target": "code1", "line_number": 0, "color": "yellow", "duration": 0.3},
            {"type": "wait", "duration": 0.3},
            {"type": "highlight_code_line", "target": "code1", "line_number": 1, "color": "yellow", "duration": 0.3},
            {"type": "highlight", "target": "arr1", "index": _LEFT_START, "color": "blue", "duration": 0.3},
            {"type": "highlight", "target": "arr1", "index": _RIGHT_START, "color": "orange", "duration": 0.3},
            {"type": "highlight_code_line", "target": "code1", "line_number": 2, "color": "yellow", "duration": 0.3},
            # Step 1: pointers each take one step inward.
            {"type": "move_pointer", "target": "left_ptr", "index": _LEFT_START + 1, "duration": 0.5},
            {"type": "move_pointer", "target": "right_ptr", "index": _RIGHT_START - 1, "duration": 0.5},
            {"type": "highlight_code_line", "target": "code1", "line_number": 3, "color": "yellow", "duration": 0.2},
            {"type": "highlight_code_line", "target": "code1", "line_number": 4, "color": "yellow", "duration": 0.2},
            # Step 2.
            {"type": "move_pointer", "target": "left_ptr", "index": _LEFT_START + 2, "duration": 0.5},
            {"type": "move_pointer", "target": "right_ptr", "index": _RIGHT_START - 2, "duration": 0.5},
            # Step 3: they meet.
            {"type": "move_pointer", "target": "left_ptr", "index": _MEET_AT, "duration": 0.5},
            {"type": "move_pointer", "target": "right_ptr", "index": _MEET_AT, "duration": 0.5},
            # Payoff.
            {"type": "highlight", "target": "arr1", "index": _MEET_AT, "color": "gold", "duration": 0.6},
            {"type": "fade_in", "target": ["result_text"], "duration": 0.8},
            {"type": "camera_zoom", "scale": 0.6, "duration": 1.0},
            {"type": "wait", "duration": 0.8},
            {"type": "camera_zoom", "scale": 1.6667, "duration": 1.0},
            {"type": "wait", "duration": 0.3},
            {
                "type": "fade_out",
                "target": ["arr1", "code1", "left_ptr", "right_ptr", "caption1", "result_text"],
                "duration": 1.0,
            },
        ],
    }


def _outro_scene() -> dict:
    return {
        "id": "scene_outro",
        "type": "generic",
        "duration": 5.5,
        "narration": None,
        "elements": [
            {"type": "title", "id": "outro_title", "content": "Thanks for Watching", "font_size": 48, "color": "white"},
            {
                "type": "subtitle",
                "id": "outro_subtitle",
                "content": "DSA Video Studio - Platform Demo",
                "font_size": 28,
                "color": "gray",
            },
        ],
        "actions": [
            {"type": "fade_in", "target": ["outro_title"], "duration": 1.0},
            {"type": "wait", "duration": 0.8},
            {"type": "fade_in", "target": ["outro_subtitle"], "duration": 0.8},
            {"type": "wait", "duration": 1.0},
            {"type": "fade_out", "target": ["outro_title", "outro_subtitle"], "duration": 1.0},
        ],
    }
