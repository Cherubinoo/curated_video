"""Fixed, deterministic branding outro appended to every generated video -
never left to chance by asking the model to remember it. Same trust
philosophy as demo_specification.py: this is hand-authored, reviewed
content, not AI output, so it's exempt from the retry/validation gate the
model's own scenes go through (it's appended after that gate passes).
"""
from __future__ import annotations

BRAND_NAME = "Code2Day Learning"
PRODUCT_OF = "A product of Tera2Nano"

_BRANDING_NARRATION = f"This video was brought to you by {BRAND_NAME}, {PRODUCT_OF}."

_SCENE_ID = "code2day_branding_outro"


def build_branding_scene() -> dict:
    """A short, static end card - two lines of text, fade in and hold.
    Narration (~13 words, ~5.2s to speak) is paced to roughly match its own
    4.3s of actions, consistent with the same narration-to-action pacing
    every other scene is held to (see bedrock_specification_generator.py's
    _scene_pacing_problems) even though this scene itself is never fed
    through that validation gate."""
    return {
        "id": _SCENE_ID,
        "type": "generic",
        "duration": 4.3,
        "narration": _BRANDING_NARRATION,
        "elements": [
            {
                "type": "title",
                "id": "brand_title",
                "content": BRAND_NAME,
                "font_size": 54,
                "color": "white",
                "position": {"kind": "coordinate", "x": 0, "y": 1.5},
            },
            {
                "type": "subtitle",
                "id": "brand_subtitle",
                "content": PRODUCT_OF,
                "font_size": 30,
                "color": "gray",
                "position": {"kind": "coordinate", "x": 0, "y": 0.3},
            },
        ],
        "actions": [
            {"type": "fade_in", "target": ["brand_title"], "duration": 1.0},
            {"type": "wait", "duration": 0.3},
            {"type": "fade_in", "target": ["brand_subtitle"], "duration": 1.0},
            {"type": "wait", "duration": 2.0},
        ],
    }


def append_branding(raw_specification: dict) -> dict:
    """Appends the branding scene and its narration to an already-assembled
    raw specification dict (either a real generated one or the demo
    fallback) - called once, right before final validation, so branding is
    on every video regardless of which path produced the rest of it."""
    raw_specification = dict(raw_specification)
    raw_specification["scenes"] = list(raw_specification.get("scenes") or []) + [build_branding_scene()]

    audio = dict(raw_specification.get("audio") or {})
    existing_script = audio.get("narration_script")
    audio["narration_script"] = (
        f"{existing_script.strip()} {_BRANDING_NARRATION}" if existing_script else _BRANDING_NARRATION
    )
    audio["enabled"] = True
    raw_specification["audio"] = audio

    return raw_specification
