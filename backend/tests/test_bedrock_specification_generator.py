"""BedrockSpecificationGenerator's generate -> validate -> retry-with-
feedback -> fall back to the deterministic demo pipeline. Mocks
`_call_bedrock` directly (returns the model's raw text or None) rather than
boto3 itself, so these stay fast and never touch the network - the real
Bedrock call is covered by the live verification in README.md.
"""
from __future__ import annotations

import copy
import json
from unittest.mock import patch

from app.services.ai.bedrock_specification_generator import (
    _MAX_ATTEMPTS,
    _SYSTEM_PROMPT,
    BedrockSpecificationGenerator,
    _combined_narration,
    _estimate_action_seconds,
    _max_tokens_for_duration,
    _scene_pacing_problems,
    _target_min_scene_count,
    _target_word_count,
    _timeout_for_max_tokens,
)
from app.services.ai.branding import _BRANDING_NARRATION, _SCENE_ID as _BRANDING_SCENE_ID

_DEMO_SCENE_IDS_WITH_BRANDING = {"scene_intro", "scene_main", "scene_outro", _BRANDING_SCENE_ID}

# Narration word counts below are deliberately calibrated (words/2.5 seconds
# to speak) to land within each scene's own action-time pacing window
# (0.35x-1.8x, see _scene_pacing_problems) - scene_1's 10s of actions needs
# 8.75-45 words (16 used), scene_2's 15s needs 13.1-67.5 words (21 used).
_VALID_MODEL_OUTPUT = {
    "title": "Sliding Window Basics",
    "scenes": [
        {
            "id": "scene_1",
            "type": "generic",
            "duration": 6,
            "narration": "Let's look at the sliding window technique on a small array and see how it works.",
            "elements": [
                {"type": "title", "id": "t1", "content": "Sliding Window", "font_size": 48, "color": "white"}
            ],
            "actions": [{"type": "write", "target": ["t1"], "duration": 10.0}],
        },
        {
            "id": "scene_2",
            "type": "array",
            "duration": 6,
            "narration": (
                "It avoids recomputing sums for every subarray by reusing the previous window's "
                "total and adjusting it incrementally as the window slides."
            ),
            "elements": [
                {
                    "type": "array",
                    "id": "arr1",
                    "values": [1, 2, 3, 4, 5],
                    "cell_size": 1.0,
                    "color": "white",
                    "position": {"kind": "coordinate", "x": 0, "y": 0},
                }
            ],
            "actions": [
                # Durations chosen so total action time (10+10+5=25s) clears
                # _MIN_DURATION_COVERAGE_RATIO's threshold at the
                # duration_target=30 used by most tests below - otherwise
                # this "valid" fixture would itself be rejected as too short.
                {"type": "create", "target": ["arr1"], "duration": 10.0},
                {"type": "highlight", "target": "arr1", "index": 0, "color": "yellow", "duration": 5.0},
            ],
        },
    ],
}
_VALID_COMBINED_NARRATION = " ".join(s["narration"] for s in _VALID_MODEL_OUTPUT["scenes"])

# duration=16 clears the duration-coverage threshold at duration_target=20
# (used below), and the narration's ~17 words (~6.8s to speak) stays within
# that scene's 0.35x-1.8x pacing window (5.6s-28.8s) - this fixture exists
# to exercise the "invalid element reference" validation-error path
# specifically, not the duration-coverage or pacing checks.
_INVALID_MODEL_OUTPUT = {
    "title": "Broken",
    "scenes": [
        {
            "id": "scene_1",
            "type": "generic",
            "duration": 4,
            "narration": (
                "This references an element that doesn't exist, which should fail semantic "
                "validation and trigger a corrective retry."
            ),
            "elements": [],
            "actions": [{"type": "highlight", "target": "does_not_exist", "duration": 16.0}],
        }
    ],
}


def _text(payload: dict) -> str:
    return json.dumps(payload)


def _with_empty_narration(payload: dict) -> dict:
    muted = copy.deepcopy(payload)
    for scene in muted["scenes"]:
        scene["narration"] = ""
    return muted


def test_valid_first_attempt_is_used_directly():
    generator = BedrockSpecificationGenerator()
    with patch.object(generator, "_call_bedrock", return_value=_text(_VALID_MODEL_OUTPUT)) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="Sliding Window Basics", topic="Sliding Window", duration_target=30
        )
    assert mock_call.call_count == 1
    assert spec.metadata.title == "Sliding Window Basics"
    # +1 for the fixed branding outro appended to every video (real or fallback).
    assert len(spec.scenes) == 3
    assert spec.scenes[-1].id == _BRANDING_SCENE_ID
    assert spec.audio.enabled is True
    assert spec.audio.narration_script == f"{_VALID_COMBINED_NARRATION} {_BRANDING_NARRATION}"
    # Each scene's own narration passes through unchanged too - this is
    # what the (currently unused) per-scene sync would key off in future.
    assert spec.scenes[0].narration == _VALID_MODEL_OUTPUT["scenes"][0]["narration"]
    assert spec.scenes[1].narration == _VALID_MODEL_OUTPUT["scenes"][1]["narration"]


def test_invalid_json_is_retried_once_then_succeeds():
    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=["not json at all", _text(_VALID_MODEL_OUTPUT)]
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="T", topic="Sliding Window", duration_target=30
        )
    assert mock_call.call_count == 2
    assert len(spec.scenes) == 3


def test_invalid_specification_falls_back_to_demo_after_exhausting_retries():
    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator,
        "_call_bedrock",
        side_effect=[_text(_INVALID_MODEL_OUTPUT)] * _MAX_ATTEMPTS,
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="Fallback Title", topic="demo", duration_target=20
        )
    assert mock_call.call_count == _MAX_ATTEMPTS
    # Fell back to the deterministic demo shell - recognizable by its scene ids.
    assert {s.id for s in spec.scenes} == _DEMO_SCENE_IDS_WITH_BRANDING
    assert spec.metadata.title == "Fallback Title"


def test_bedrock_failure_on_every_attempt_falls_back_to_demo():
    generator = BedrockSpecificationGenerator()
    with patch.object(generator, "_call_bedrock", return_value=None) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="T", topic="demo", duration_target=20
        )
    assert mock_call.call_count == _MAX_ATTEMPTS
    assert {s.id for s in spec.scenes} == _DEMO_SCENE_IDS_WITH_BRANDING


def test_bedrock_failure_is_retried_then_succeeds():
    """Regression test for a real observed bug: a single Bedrock request
    that timed out (transient slowness, not a permanent auth/config
    failure) used to fall back to the generic demo immediately, discarding
    the rest of the retry budget. A failed call must be retried like any
    other recoverable failure."""
    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[None, _text(_VALID_MODEL_OUTPUT)]
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="T", topic="Sliding Window", duration_target=30
        )
    assert mock_call.call_count == 2
    assert len(spec.scenes) == 3


def test_missing_narration_is_retried_then_succeeds():
    """Regression test for a real observed failure: a model response had
    valid `scenes` (passed validate_specification on the first try) but
    empty/missing narration on every scene, silently producing a mute video
    with no error anywhere. Missing narration must now trigger the same
    corrective retry as invalid JSON/scenes, not slip through."""
    mute_output = _with_empty_narration(_VALID_MODEL_OUTPUT)
    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(mute_output), _text(_VALID_MODEL_OUTPUT)]
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="T", topic="Sliding Window", duration_target=30
        )
    assert mock_call.call_count == 2
    assert spec.audio.enabled is True
    assert spec.audio.narration_script == f"{_VALID_COMBINED_NARRATION} {_BRANDING_NARRATION}"
    second_call_messages = mock_call.call_args_list[1].args[0]
    feedback_text = second_call_messages[-1]["content"]
    assert "narration" in feedback_text.lower()


def test_narration_missing_on_every_attempt_falls_back_to_demo():
    mute_output = _with_empty_narration(_VALID_MODEL_OUTPUT)
    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(mute_output)] * _MAX_ATTEMPTS
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="Fallback Title", topic="demo", duration_target=20
        )
    assert mock_call.call_count == _MAX_ATTEMPTS
    assert {s.id for s in spec.scenes} == _DEMO_SCENE_IDS_WITH_BRANDING
    # The demo fallback always has its own real narration - never silently mute.
    assert spec.audio.enabled is True
    assert spec.audio.narration_script


def test_estimate_action_seconds_sums_duration_and_wait_after():
    candidate = {
        "scenes": [
            {"actions": [{"duration": 2.0, "wait_after": 0.5}, {"duration": 1.0}]},
            {"actions": [{"duration": 3.0, "wait_after": 1.0}]},
        ]
    }
    # 2.0+0.5 + 1.0+0.0 + 3.0+1.0 = 7.5
    assert _estimate_action_seconds(candidate) == 7.5


def test_estimate_action_seconds_defaults_missing_fields():
    # Missing "duration"/"wait_after" fall back to the schema defaults
    # (1.0/0.0) rather than crashing or counting as zero.
    candidate = {"scenes": [{"actions": [{}, {}]}]}
    assert _estimate_action_seconds(candidate) == 2.0


def test_animation_too_short_is_retried_then_succeeds():
    """Regression test for a real observed bug: two generated videos had
    their animation run for only 33-59% of the narration's length (48s of
    real animation for 134.6s of narration is the extreme case) because
    nothing checked that the actions actually added up to the requested
    duration - the model's scene "duration" field is just a label, never
    enforced by the renderer. A too-short animation must now trigger the
    same corrective retry as invalid JSON/scenes/missing narration."""
    too_short = json.loads(_text(_VALID_MODEL_OUTPUT))
    too_short["scenes"][0]["actions"] = [{"type": "write", "target": ["t1"], "duration": 1.0}]
    too_short["scenes"][1]["actions"] = [{"type": "create", "target": ["arr1"], "duration": 1.0}]
    # total = 2.0s, nowhere near 0.7 * duration_target=30 = 21s - reported
    # before the (also now-failing) per-scene pacing check, since the
    # if/elif chain checks duration-coverage first.

    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(too_short), _text(_VALID_MODEL_OUTPUT)]
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="T", topic="Sliding Window", duration_target=30
        )
    assert mock_call.call_count == 2
    assert len(spec.scenes) == 3
    second_call_messages = mock_call.call_args_list[1].args[0]
    feedback_text = second_call_messages[-1]["content"]
    assert "too short" in feedback_text.lower()
    assert "30 seconds" in feedback_text


def test_animation_too_short_on_every_attempt_falls_back_to_demo():
    too_short = json.loads(_text(_VALID_MODEL_OUTPUT))
    too_short["scenes"][0]["actions"] = [{"type": "write", "target": ["t1"], "duration": 1.0}]
    too_short["scenes"][1]["actions"] = [{"type": "create", "target": ["arr1"], "duration": 1.0}]

    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(too_short)] * _MAX_ATTEMPTS
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="Fallback Title", topic="demo", duration_target=30
        )
    assert mock_call.call_count == _MAX_ATTEMPTS
    assert {s.id for s in spec.scenes} == _DEMO_SCENE_IDS_WITH_BRANDING


def test_scene_pacing_problems_flags_narration_much_longer_than_its_actions():
    """Regression test for the actual reported bug: "video is going
    somewhere and audio somewhere" - narration is muxed as one continuous
    track over the whole video with no per-scene sync anchor, so if one
    scene's narration takes much longer to speak than that scene's actions
    take to play, the mismatch compounds and the audio drifts ahead of (or
    behind) what's actually on screen for the rest of the video."""
    candidate = {
        "scenes": [
            {
                "id": "slow_scene",
                "narration": "word " * 60,  # 60 words / 2.5 = 24s to speak
                "actions": [{"duration": 2.0}],  # only 2s of actions - ratio 12.0, way over 1.8
            }
        ]
    }
    problems = _scene_pacing_problems(candidate)
    assert len(problems) == 1
    assert "slow_scene" in problems[0]


def test_scene_pacing_problems_flags_narration_much_shorter_than_its_actions():
    candidate = {
        "scenes": [
            {
                "id": "quiet_scene",
                "narration": "Short line.",  # 2 words / 2.5 = 0.8s to speak
                "actions": [{"duration": 20.0}],  # 20s of actions - ratio 0.04, way under 0.35
            }
        ]
    }
    problems = _scene_pacing_problems(candidate)
    assert len(problems) == 1
    assert "quiet_scene" in problems[0]


def test_scene_pacing_problems_ignores_scenes_with_no_narration():
    candidate = {"scenes": [{"id": "silent", "narration": None, "actions": [{"duration": 1.0}]}]}
    assert _scene_pacing_problems(candidate) == []


def test_scene_pacing_problems_empty_for_well_paced_scenes():
    assert _scene_pacing_problems(_VALID_MODEL_OUTPUT) == []


def test_combined_narration_joins_scene_narration_in_order():
    candidate = {
        "scenes": [
            {"narration": "First."},
            {"narration": None},
            {"narration": "  "},
            {"narration": "Second."},
        ]
    }
    assert _combined_narration(candidate) == "First. Second."


def test_scene_pacing_mismatch_is_retried_then_succeeds():
    mismatched = json.loads(_text(_VALID_MODEL_OUTPUT))
    mismatched["scenes"][0]["narration"] = "word " * 60  # 24s to speak vs. scene_1's 10s of actions

    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(mismatched), _text(_VALID_MODEL_OUTPUT)]
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="T", topic="Sliding Window", duration_target=30
        )
    assert mock_call.call_count == 2
    assert len(spec.scenes) == 3
    second_call_messages = mock_call.call_args_list[1].args[0]
    feedback_text = second_call_messages[-1]["content"]
    assert "sync" in feedback_text.lower() or "scene_1" in feedback_text


def test_scene_pacing_mismatch_on_every_attempt_falls_back_to_demo():
    mismatched = json.loads(_text(_VALID_MODEL_OUTPUT))
    mismatched["scenes"][0]["narration"] = "word " * 60

    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(mismatched)] * _MAX_ATTEMPTS
    ) as mock_call:
        spec = generator.generate_specification(
            "Explain sliding window", title="Fallback Title", topic="demo", duration_target=30
        )
    assert mock_call.call_count == _MAX_ATTEMPTS
    assert {s.id for s in spec.scenes} == _DEMO_SCENE_IDS_WITH_BRANDING


def test_duration_scaling_grows_with_longer_requested_videos():
    """Regression coverage for a real observed bug: narration/scene-count
    guidance and the completion token budget used to be fixed regardless of
    the requested duration, so a 5-10 minute request got the same short
    output as a 90s one (and, separately, got silently truncated once the
    budget was raised without matching headroom - see the docstrings on
    these functions for the live-measured numbers this is calibrated
    against)."""
    assert _target_word_count(90) < _target_word_count(300) < _target_word_count(600)
    assert _target_min_scene_count(90) < _target_min_scene_count(300) < _target_min_scene_count(600)
    assert _max_tokens_for_duration(90) < _max_tokens_for_duration(300) <= _max_tokens_for_duration(600)
    # Floors/ceilings still apply at the extremes.
    # Floors are high enough to cover the mandatory 17-point content
    # outline (see _SYSTEM_PROMPT) even at a trivially short duration.
    assert _target_word_count(1) >= 280
    assert _target_min_scene_count(1) >= 10
    assert _max_tokens_for_duration(1) >= 9000
    assert _max_tokens_for_duration(10_000) <= 24000


def test_timeout_scales_with_token_budget_and_is_floored_and_capped():
    assert _timeout_for_max_tokens(6000) == 180.0  # floor
    assert _timeout_for_max_tokens(24000) == 480.0  # ceiling well above the live-observed ~260s
    assert _timeout_for_max_tokens(6000) < _timeout_for_max_tokens(16000) < _timeout_for_max_tokens(24000)


def test_user_message_includes_duration_scaled_targets():
    generator = BedrockSpecificationGenerator()
    with patch.object(generator, "_call_bedrock", return_value=_text(_VALID_MODEL_OUTPUT)) as mock_call:
        generator.generate_specification("prompt", title="T", topic="Quick Sort", duration_target=300)

    first_call_messages = mock_call.call_args_list[0].args[0]
    user_content = first_call_messages[0]["content"]
    assert str(_target_word_count(300)) in user_content
    assert str(_target_min_scene_count(300)) in user_content


def test_system_prompt_includes_the_mandatory_17_point_content_outline():
    """Every topic requested must cover this fixed curriculum - a direct
    user requirement, not just "story + concept" framing."""
    required_points = [
        "What is it?",
        "Why do we need it?",
        "Basic intuition",
        "How it works",
        "Important rules",
        "Visual example",
        "Step-by-step execution",
        "Why the algorithm works",
        "Variations/types",
        "Pseudocode",
        "Python implementation",
        "Common problem patterns",
        "When to recognize it",
        "Common mistakes",
        "Time complexity",
        "Space complexity",
        "Final mental model",
    ]
    for point in required_points:
        assert point in _SYSTEM_PROMPT


def test_second_bedrock_call_receives_the_validation_errors_as_feedback():
    generator = BedrockSpecificationGenerator()
    with patch.object(
        generator, "_call_bedrock", side_effect=[_text(_INVALID_MODEL_OUTPUT), _text(_VALID_MODEL_OUTPUT)]
    ) as mock_call:
        generator.generate_specification("prompt", title="T", topic="demo", duration_target=20)

    assert mock_call.call_count == 2
    second_call_messages = mock_call.call_args_list[1].args[0]
    feedback_text = second_call_messages[-1]["content"]
    assert "invalid" in feedback_text.lower()
    assert "does_not_exist" in feedback_text or "unknown element id" in feedback_text.lower()
