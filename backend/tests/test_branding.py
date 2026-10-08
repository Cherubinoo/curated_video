"""`append_branding()` - the fixed, deterministic branding outro added to
every generated video (real or fallback) per an explicit request that
videos consistently credit Code2Day Learning / Tera2Nano at the end,
rather than leaving it to chance whether the model's own outro mentions
it. Pure dict manipulation, no rendering involved - stays fast.
"""
from __future__ import annotations

from animation_engine.validators.specification_validator import validate_specification
from app.services.ai.branding import (
    BRAND_NAME,
    PRODUCT_OF,
    _BRANDING_NARRATION,
    _SCENE_ID,
    append_branding,
    build_branding_scene,
)
from app.services.ai.demo_specification import build_demo_specification


def test_build_branding_scene_is_schema_valid_standalone():
    scene = build_branding_scene()
    assert scene["id"] == _SCENE_ID
    assert BRAND_NAME in scene["narration"]
    assert PRODUCT_OF in scene["narration"]


def test_append_branding_adds_one_scene_at_the_end():
    raw = build_demo_specification()
    original_count = len(raw["scenes"])
    branded = append_branding(raw)
    assert len(branded["scenes"]) == original_count + 1
    assert branded["scenes"][-1]["id"] == _SCENE_ID


def test_append_branding_does_not_mutate_the_input():
    raw = build_demo_specification()
    original_scene_count = len(raw["scenes"])
    append_branding(raw)
    assert len(raw["scenes"]) == original_scene_count  # caller's dict untouched


def test_append_branding_appends_to_existing_narration():
    raw = build_demo_specification(narration="Existing narration.", voice_provider="polly")
    branded = append_branding(raw)
    assert branded["audio"]["narration_script"] == f"Existing narration. {_BRANDING_NARRATION}"
    assert branded["audio"]["enabled"] is True


def test_append_branding_sets_narration_when_none_existed():
    raw = build_demo_specification()  # no narration by default
    branded = append_branding(raw)
    assert branded["audio"]["narration_script"] == _BRANDING_NARRATION
    assert branded["audio"]["enabled"] is True


def test_branded_demo_specification_is_schema_valid():
    raw = build_demo_specification(narration="Some narration.", voice_provider="polly")
    branded = append_branding(raw)
    result = validate_specification(branded)
    assert result.is_valid, result.errors
    assert result.specification.scenes[-1].id == _SCENE_ID
