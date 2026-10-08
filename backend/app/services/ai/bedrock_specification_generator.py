"""VideoSpecificationGenerator backed by AWS Bedrock.

Asks the model for a complete, topic-driven VideoSpecification - scenes,
elements, actions, and narration - not just narration text. Narration is
written PER SCENE (not one flat script) and validated to stay paced with
that scene's own actions (see `_scene_pacing_problems`) - otherwise the
single audio track assembled from it drifts out of sync with what's on
screen as the video goes on, a real observed bug. This is the real
integration point the product spec's architecture was built for: the
model's output is NEVER trusted directly. It always passes through the
exact same `validate_specification()` trust boundary as every other
specification in this system (hand-authored or generated), and if it
doesn't validate, we send the errors back to the model for one corrective
retry before giving up. A render must never fail, and must never execute
anything the model wrote, just because generation had a bad day - see
`generate_specification()`'s fallback to the deterministic demo.

Calls Bedrock through `app.services.ai.bedrock_client` (the Mantle gateway -
see that module's docstring for why this project uses it instead of the
native bedrock-runtime Converse API).
"""
from __future__ import annotations

import json
import re

from app.core.logging import get_logger
from app.schemas.specification import VideoSpecification
from app.services.ai.bedrock_client import call_bedrock_chat
from app.services.ai.branding import append_branding
from app.services.ai.demo_specification import build_demo_specification
from app.services.ai.dsl_reference import DSL_REFERENCE
from app.services.ai.specification_generator import (
    SpecificationGenerationError,
    VideoSpecificationGenerator,
)
from app.services.audio import get_voice_provider_name
from animation_engine.validators.specification_validator import validate_specification

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are the specification generator for DSA Video Studio, a platform that renders "
    "educational programming/data-structures-and-algorithms concept videos with Manim, ranging "
    "from short 60-second explainers up to full 10-minute deep dives depending on what's "
    "requested. Given a title, topic, target duration, and a description/prompt from the admin, you "
    "produce a complete, valid video specification that actually visualizes and narrates that "
    "specific topic - arrays, pointers, code, highlights, camera moves - not a generic placeholder. "
    "Be concrete: use real example values (e.g. an actual array of numbers relevant to the topic), "
    "real code lines, and narration that would genuinely teach a beginner the concept.\n\n"
    "Every video must work on TWO levels at once, not just one:\n"
    "  1. STORY: a clear beginning, middle, and end - open with a concrete problem or question "
    "(not a dry definition), build through the technique step by step as if walking the viewer "
    "through solving it live, hit a genuine payoff moment (the answer found, the pattern revealed, "
    "the \"aha\"), and close by tying it back to why the technique matters. Scenes should feel like "
    "they're building on each other, not like an unordered list of facts.\n"
    "  2. CONCEPT: the narration must be technically accurate and actually teach the mechanism - "
    "state what problem is being solved, why the naive approach is worse, and how each step of the "
    "algorithm works, using the specific numbers/code visible on screen at that moment. A viewer who "
    "has never seen this topic before should be able to explain it back after watching.\n"
    "Neither half is optional: flashy motion with no real explanation is as much a failure as an "
    "accurate but static/boring wall of facts.\n\n"
    "*** MANDATORY CONTENT OUTLINE - every single topic requested, no matter what it is, must cover "
    "ALL 17 of these points somewhere in the video's scenes/narration, in roughly this order. This is "
    "a hard content requirement, not a suggestion - skipping any point is a failure even if the "
    "video looks polished otherwise: ***\n"
    "  1. What is it? - a one-sentence definition of the technique/structure.\n"
    "  2. Why do we need it? - the problem it solves and what's inefficient/awkward without it.\n"
    "  3. Basic intuition - the core insight in plain language, no jargon yet.\n"
    "  4. How it works - the mechanism, step by step, in general terms.\n"
    "  5. Important rules - the constraints/preconditions that make it valid (e.g. \"array must be "
    "sorted\") and any invariants it maintains throughout.\n"
    "  6. Visual example - a concrete array/structure with real values shown on screen.\n"
    "  7. Step-by-step execution - actually animate that example running to completion.\n"
    "  8. Why the algorithm works - the justification/proof intuition for why this approach is "
    "correct, not just what it does.\n"
    "  9. Variations/types - related forms or common tweaks of the technique, briefly.\n"
    "  10. Pseudocode - a short, language-agnostic code_block.\n"
    "  11. Python implementation - a short, real, runnable-looking Python code_block.\n"
    "  12. Common problem patterns - what kinds of problems this technique tends to solve.\n"
    "  13. When to recognize it - concrete signals in a problem statement that hint this technique "
    "applies (e.g. \"sorted array\" + \"pair/triplet\" -> two pointers).\n"
    "  14. Common mistakes - at least one real pitfall beginners hit (off-by-one, wrong pointer "
    "moved, wrong base case, etc.).\n"
    "  15. Time complexity - stated and briefly justified, not just asserted.\n"
    "  16. Space complexity - stated and briefly justified.\n"
    "  17. Final mental model - a memorable one- or two-sentence summary to close on.\n"
    "How to fit this in: group naturally-adjacent points into the same scene rather than forcing 17 "
    "separate scenes (e.g. 15+16 often fit one scene together; 10+11 often fit one scene together; "
    "1+2+3 can open together). For a short requested duration, cover every point CONCISELY rather "
    "than dropping any of them; for a longer duration, give each point more room and more examples. "
    "The requested scene count and word count in the user message already account for fitting all 17 "
    "points in - use them as your budget.\n\n"
    + DSL_REFERENCE
)

_MAX_ATTEMPTS = 4  # 1 initial generation + 3 corrective retries on validation failure
# A 3rd attempt was tried once before and reverted for latency - at the
# time, most failures were raw "not valid JSON" (the model's free-text
# output getting cut off/malformed), which a retry basically never fixes,
# so a 3rd attempt was pure wasted latency. Now that `_call_bedrock` uses
# Bedrock's `response_format: json_object` mode (guarantees syntactically
# valid JSON - see bedrock_client.py), that failure mode is gone; what's
# left are genuine semantic validation errors (bad references, wrong
# action/element vocabulary), which the retry-feedback loop demonstrably
# converges on (observed: 17 errors -> 5 different errors after one
# retry). A 4th attempt was added on top of that once the mandatory
# 17-point content outline made narration-to-action pacing genuinely
# harder to get right in one pass (live-observed: attempt 0 fixed a
# duration-coverage problem, attempt 1 then surfaced specific per-scene
# pacing mismatches with real numbers) - each round demonstrably narrows
# the problem rather than repeating the same failure, so the extra
# ~60-260s is worth it here too, same reasoning as the 3rd attempt above.
_MAX_ERRORS_IN_FEEDBACK = 8
# A real narration script for a 60-150s video is easily 100+ words - this is
# just a floor to catch "narration" being missing/null/a one-liner, which
# otherwise passes JSON parsing fine and silently produces a mute video (a
# real failure mode observed: valid scenes, empty narration, no error).
_MIN_NARRATION_CHARS = 60
# Two real generated videos had their animation run for only 33-59% of the
# narration's actual length (48s of animation for 134.6s of narration; 86.3s
# for 146.8s) - asking nicely in the prompt for scene "duration" fields to
# sum near the target wasn't enough on its own, the model just didn't do it
# reliably. This estimates real playtime the same way the renderer does -
# summing each action's actual duration+wait_after, not the scene's
# self-reported (and unenforced) "duration" field - and rejects a spec that
# falls well short, the same hard-validate-and-retry pattern already used
# for coordinate bounds/code_block size/narration presence. The renderer
# pads a short animation to match a longer narration (never truncates it -
# see FFmpegService) rather than fail, but too much of that padding just
# means "no animation" for a big chunk of the video - a real complaint.
_MIN_DURATION_COVERAGE_RATIO = 0.7

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

# Narrates the actual on-screen content of the bundled demo shell (see
# demo_specification.py's _main_scene) so the fallback is never a silent
# video either - it's only used when Bedrock is unreachable or can't
# produce a valid spec+narration after a retry, but "AI is down" still
# shouldn't mean "ship a mute video".
_DEMO_FALLBACK_NARRATION = (
    "This is the DSA Video Studio platform demo. Watch two pointers start at opposite "
    "ends of the array, one from the left and one from the right, stepping inward "
    "together as the code below runs. Each step brings them closer until they meet in "
    "the middle - the two-pointer pattern for scanning an array from both ends in a "
    "single pass."
)


def _target_word_count(duration_target: int) -> int:
    """~150 words/minute is a natural spoken narration pace (matches Polly's
    default cadence) - 2.5 words/sec. Used to tell the model concretely how
    much narration a given duration actually needs, instead of a fixed
    word-count range that was tuned for the old ~90s default and produced
    videos that were too short once duration could go up to 10 minutes.
    Floor of 280 (not the old 150) accounts for the mandatory 17-point
    content outline (see _SYSTEM_PROMPT) - even briefly touching all 17
    points takes real words, regardless of how short the requested
    duration is."""
    return max(280, round(duration_target * 2.5))


def _target_min_scene_count(duration_target: int) -> int:
    """Roughly one scene per 20 seconds of target duration - enough for each
    scene to cover one real sub-step without being rushed or padded. Floor
    of 10 (not the old 4) leaves enough room to cover the mandatory 17-point
    content outline even with natural grouping (e.g. time+space complexity
    sharing a scene, pseudocode+Python sharing a scene) - 4 scenes can't
    realistically touch all 17 points without skipping most of them."""
    return max(10, round(duration_target / 20))


def _scene_action_seconds(scene: dict) -> float:
    """Sums a single scene's actions' actual duration+wait_after the same
    way the renderer plays them back (see scene_builder.py's construct
    loop) - NOT the scene's self-reported "duration" field, which is just a
    label the renderer never enforces."""
    total = 0.0
    for action in scene.get("actions") or []:
        if not isinstance(action, dict):
            continue
        duration = action.get("duration")
        duration = duration if isinstance(duration, (int, float)) else 1.0
        wait_after = action.get("wait_after")
        wait_after = wait_after if isinstance(wait_after, (int, float)) else 0.0
        total += duration + wait_after
    return total


def _estimate_action_seconds(candidate: dict) -> float:
    """This is what actually determines how long the rendered animation
    runs before the audio/video padding fallback kicks in."""
    return sum(
        _scene_action_seconds(scene) for scene in candidate.get("scenes") or [] if isinstance(scene, dict)
    )


_WORDS_PER_SECOND = 2.5  # ~150 words/minute - matches _target_word_count's assumption
_PACING_RATIO_MAX = 1.8
_PACING_RATIO_MIN = 0.35


def _scene_pacing_problems(candidate: dict) -> list[str]:
    """The real cause of audio/video drift: narration is a single track
    played alongside the whole video with no per-scene sync anchor, so if
    one scene's narration takes much longer (or shorter) to speak than that
    scene's own actions take to play, the mismatch compounds through every
    later scene - by the end, the narration can be describing something
    completely different from what's on screen. This can't be caught by
    checking the TOTAL narration length against the TOTAL video length
    (both fixes already in place) - a video can match perfectly in total
    while being badly out of sync scene by scene. Returns a description per
    offending scene, or an empty list if every scene's pacing is reasonable.
    A scene with no narration of its own is exempt - nothing to drift."""
    problems = []
    for scene in candidate.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        narration = scene.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            continue
        est_speak_seconds = len(narration.split()) / _WORDS_PER_SECOND
        est_action_seconds = _scene_action_seconds(scene)
        if est_action_seconds <= 0:
            problems.append(
                f"scene '{scene.get('id', '?')}' has narration (~{est_speak_seconds:.0f}s to speak) "
                "but no actions at all to play alongside it"
            )
            continue
        ratio = est_speak_seconds / est_action_seconds
        if ratio > _PACING_RATIO_MAX or ratio < _PACING_RATIO_MIN:
            problems.append(
                f"scene '{scene.get('id', '?')}': narration needs ~{est_speak_seconds:.0f}s to speak "
                f"but its actions only take ~{est_action_seconds:.0f}s to play"
            )
    return problems


def _combined_narration(candidate: dict) -> str:
    """The single audio track actually synthesized is still one continuous
    script (see workers/tasks.py) - assembled here from each scene's own
    narration, in scene order, now that pacing is validated per scene."""
    parts = []
    for scene in candidate.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        narration = scene.get("narration")
        if isinstance(narration, str) and narration.strip():
            parts.append(narration.strip())
    return " ".join(parts)


def _max_tokens_for_duration(duration_target: int) -> int:
    """Scales the completion token budget with the requested duration so a
    long video's scenes/actions/narration don't get cut off mid-JSON.
    Calibrated against live usage, not a guess: a 90s request used ~3.7K
    completion tokens, a 300s request used ~13.5K, a 600s request used
    ~16K. The multiplier gives real headroom above those observed numbers,
    since running out of budget silently truncates the JSON and burns a
    whole ~60-260s round trip for nothing. Floor raised from 6000 to 9000
    since the mandatory 17-point content outline means even a short/default
    duration now produces at least 10 scenes (up from ~5-6) - more content
    than the original 90s calibration point assumed."""
    return min(24000, max(9000, round(duration_target * 55)))


def _timeout_for_max_tokens(max_tokens: int) -> float:
    """A live-verified 600s-duration request (~16K completion tokens) took
    ~260s end to end - the shared client's 180s default is nowhere near
    enough for that. Assumes a conservative ~40 tokens/sec worst-case
    throughput (observed was closer to 60/sec) so slower runs still finish
    within the timeout instead of being cut off and wasting the attempt."""
    return min(480.0, max(180.0, max_tokens / 40))


class BedrockSpecificationGenerator(VideoSpecificationGenerator):
    def generate_specification(
        self, prompt: str, *, title: str, topic: str, duration_target: int
    ) -> VideoSpecification:
        raw = self._generate_with_retry(prompt, title=title, topic=topic, duration_target=duration_target)
        if raw is None:
            logger.warning(
                "bedrock_spec_generation_falling_back_to_demo",
                topic=topic,
                reason="Bedrock unreachable or could not produce a valid specification after retry.",
            )
            raw = build_demo_specification(
                title=title,
                topic=topic,
                duration_target=duration_target,
                narration=_DEMO_FALLBACK_NARRATION,
                voice_provider=get_voice_provider_name(),
            )

        raw = append_branding(raw)
        result = validate_specification(raw)
        if not result.is_valid:
            # Only the demo-shell fallback reaches here un-pre-validated,
            # and we control that shell end to end - this would be a bug.
            raise SpecificationGenerationError(
                "Specification failed validation (this is a bug).", errors=result.errors
            )
        return result.specification

    def _generate_with_retry(
        self, prompt: str, *, title: str, topic: str, duration_target: int
    ) -> dict | None:
        target_words = _target_word_count(duration_target)
        target_scenes = _target_min_scene_count(duration_target)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Title: {title}\nTopic: {topic}\nTarget total video duration: "
                    f"~{duration_target} seconds\nAdmin's prompt/description:\n{prompt}\n\n"
                    f"This video needs to actually fill ~{duration_target} seconds: aim for roughly "
                    f"{target_words} words of real, substantive narration (not padding or repeated "
                    f"phrasing - every sentence should teach something) and at least {target_scenes} "
                    "scenes so there's enough real content and motion to cover the full requested "
                    f"duration. Critically, the scenes' \"duration\" fields, summed together, must add "
                    f"up to approximately {duration_target} seconds too - if the animation runs "
                    "noticeably shorter than the narration, the video ends up mostly a frozen frame "
                    "while the audio keeps playing, which looks broken. If you have more to say than "
                    "the visuals naturally take, slow the pacing down (longer action durations, more "
                    "wait_after between beats, an extra worked example) rather than rushing through "
                    "scenes quickly and leaving the rest of the narration to play over a static "
                    "screen.\n\nGenerate the JSON now."
                ),
            }
        ]

        for attempt in range(_MAX_ATTEMPTS):
            text = self._call_bedrock(messages, duration_target=duration_target)
            if text is None:
                # Covers no API key configured, network errors, AND request
                # timeouts - a real observed case was a single slow Bedrock
                # response timing out and falling back to the generic demo
                # immediately, discarding the rest of the retry budget for
                # what was likely just transient slowness. Retrying costs
                # little for a genuinely permanent failure (missing API key/
                # bad auth return near-instantly) and is the only way to
                # recover from a transient one - so try again with the same
                # request rather than giving up on the first failure.
                logger.warning("bedrock_call_failed", attempt=attempt)
                continue

            candidate = self._parse_model_json(text)
            has_valid_shape = candidate is not None and isinstance(candidate.get("scenes"), list)
            combined_narration = _combined_narration(candidate) if has_valid_shape else ""
            has_narration = len(combined_narration.strip()) >= _MIN_NARRATION_CHARS
            estimated_seconds = _estimate_action_seconds(candidate) if has_valid_shape else 0.0
            has_matching_duration = (
                not has_valid_shape  # don't double-report; the shape error takes priority below
                or estimated_seconds >= duration_target * _MIN_DURATION_COVERAGE_RATIO
            )
            pacing_problems = _scene_pacing_problems(candidate) if has_valid_shape else []
            has_good_pacing = not pacing_problems

            if not has_valid_shape or not has_narration or not has_matching_duration or not has_good_pacing:
                if not has_valid_shape:
                    reason = "not a valid JSON object with a \"scenes\" array"
                elif not has_narration:
                    reason = (
                        f"missing substantial per-scene \"narration\" text (scenes' narration "
                        f"combined must be at least {_MIN_NARRATION_CHARS} characters)"
                    )
                elif not has_matching_duration:
                    reason = (
                        f"too short: its scenes' actions only add up to about "
                        f"{estimated_seconds:.0f} seconds of real animation, but the video needs to "
                        f"be about {duration_target} seconds to match the requested duration - add "
                        "more scenes, more worked examples/edge cases, and/or longer wait_after "
                        "pauses between beats so the animation actually covers that much time; "
                        "raising the scene \"duration\" field alone does nothing, only real actions do"
                    )
                else:
                    reason = (
                        "out of sync between narration and actions in these scenes: "
                        + "; ".join(pacing_problems[:_MAX_ERRORS_IN_FEEDBACK])
                        + " - each scene's OWN narration must take about as long to speak as that "
                        "scene's OWN actions take to play (see NARRATION-TO-ACTION PACING), or the "
                        "audio ends up describing a different scene than what's on screen"
                    )
                logger.warning("bedrock_spec_not_valid_json", attempt=attempt, reason=reason)
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"That response was {reason}. Respond with ONLY the corrected, "
                            "complete JSON object (title/scenes, each scene with its own "
                            "\"narration\"), nothing else."
                        ),
                    }
                )
                continue

            raw_spec = self._assemble_specification(
                candidate, title=title, topic=topic, duration_target=duration_target
            )
            result = validate_specification(raw_spec)
            if result.is_valid:
                return raw_spec

            logger.warning(
                "bedrock_spec_validation_failed",
                attempt=attempt,
                error_count=len(result.errors),
                errors=result.errors[:_MAX_ERRORS_IN_FEEDBACK],
            )
            if attempt == _MAX_ATTEMPTS - 1:
                break
            error_text = "; ".join(result.errors[:_MAX_ERRORS_IN_FEEDBACK])
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"That specification was invalid: {error_text}. Fix these problems "
                        "and return the COMPLETE corrected JSON object (same shape - "
                        "title/scenes, each scene with its own \"narration\"), not just the fix."
                    ),
                }
            )

        return None

    def _call_bedrock(self, messages: list[dict], *, duration_target: int) -> str | None:
        # A full 3-6 scene spec + narration for a ~90s video commonly runs
        # 16-20K characters (~4-5K tokens) - 6000 gives that real headroom.
        # Longer requested durations need proportionally more scenes/actions
        # and narration, so both the completion budget AND the HTTP timeout
        # have to scale with them too, or a long video's generation either
        # gets cut off mid-JSON or times out entirely (both observed live).
        max_tokens = _max_tokens_for_duration(duration_target)
        return call_bedrock_chat(
            messages,
            system=_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=0.6,
            json_object=True,
            timeout=_timeout_for_max_tokens(max_tokens),
        )

    @staticmethod
    def _parse_model_json(text: str) -> dict | None:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _assemble_specification(
        candidate: dict, *, title: str, topic: str, duration_target: int
    ) -> dict:
        """Wraps the model's {title, scenes (each with its own narration)}
        with the metadata/settings/audio/subtitles wrapper we control
        ourselves - the model never gets to set those, keeping its job
        focused on the part that actually needs its judgment. Each scene's
        own "narration" field passes straight through unchanged (the Scene
        schema already supports it) - it's the top-level `audio.
        narration_script` that's assembled here, by joining the scenes'
        narration in order, now that per-scene pacing has been validated
        (see _scene_pacing_problems) so the joined result stays in sync
        with what's actually on screen at each point in the video."""
        narration = _combined_narration(candidate)
        return {
            "version": "1.0",
            "metadata": {
                "title": title,
                "topic": topic,
                "duration_target": duration_target,
                "difficulty": "beginner",
            },
            "settings": {"width": 1920, "height": 1080, "fps": 30, "background_color": "#0e1116"},
            "scenes": candidate.get("scenes"),
            "assets": [],
            "audio": {
                "enabled": bool(narration),
                "narration_script": narration or None,
                "voice_provider": get_voice_provider_name(),
            },
            "subtitles": {"enabled": False, "provider": "none"},
        }
