"""The topic+description -> detailed prompt step used by the New Video
form, before the normal create/generate flow ever runs."""
from __future__ import annotations

from app.services.ai.prompt_expander import PlaceholderPromptExpander


def test_placeholder_expander_includes_topic_and_description():
    expander = PlaceholderPromptExpander()
    prompt = expander.expand("Sliding Window", "Avoid recomputing subarray sums.")
    assert "Sliding Window" in prompt
    assert "Avoid recomputing subarray sums." in prompt
    assert len(prompt) > 50


def test_expand_prompt_endpoint_requires_api_key(client):
    res = client.post(
        "/api/videos/expand-prompt", json={"topic": "Recursion", "description": "Base cases."}
    )
    assert res.status_code == 401


def test_expand_prompt_endpoint_returns_prompt(client, auth_headers):
    res = client.post(
        "/api/videos/expand-prompt",
        headers=auth_headers,
        json={"topic": "Recursion", "description": "Explain base cases and the call stack."},
    )
    assert res.status_code == 200
    body = res.json()
    assert "prompt" in body
    # Case-insensitive and substantial: this may hit a real configured AI
    # provider (which could phrase it as "recursion" mid-sentence rather
    # than echoing the exact "Recursion" casing) or the deterministic
    # fallback template - either way it must be a real, on-topic prompt.
    assert "recursion" in body["prompt"].lower()
    assert len(body["prompt"]) > 50


def test_expand_prompt_endpoint_rejects_missing_fields(client, auth_headers):
    res = client.post("/api/videos/expand-prompt", headers=auth_headers, json={"topic": "Recursion"})
    assert res.status_code == 422


def test_expand_prompt_endpoint_accepts_a_long_detailed_description(client, auth_headers):
    """Regression test for a real observed crash: an admin wrote a
    genuinely detailed, multi-section description (well past the old
    2000-character cap) and the resulting 422 propagated uncaught out of
    the frontend's Server Action, crashing the whole page instead of
    showing a friendly message. `description` now matches `prompt`'s
    20000-character limit."""
    long_description = "Explain hashing thoroughly. " * 300  # ~8700 characters
    assert 2000 < len(long_description) < 20000
    res = client.post(
        "/api/videos/expand-prompt",
        headers=auth_headers,
        json={"topic": "Hash Map", "description": long_description},
    )
    assert res.status_code == 200
