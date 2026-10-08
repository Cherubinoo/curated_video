"""Shared low-level client for calling Bedrock via the "Mantle" OpenAI-
compatible gateway (`https://bedrock-mantle.<region>.api.aws/v1/chat/completions`),
authenticated with a Bedrock API key (bearer token) via a plain
`Authorization: Bearer <key>` header - no AWS SigV4 signing, no boto3.

This is deliberately NOT the standard `bedrock-runtime` Converse/InvokeModel
API. On this project's AWS account, the native Converse API returns
"Operation not allowed" for every model tested - a full account-level
Bedrock model-access restriction (see README's AI narration section) - but
the Mantle gateway works with the exact same bearer token, live-verified.
If your account has normal Bedrock model access, the native Converse API
would work too; Mantle is simply the surface proven to work on this
account, and it has the advantage of being a plain HTTPS call with no
AWS-SDK request signing to get wrong.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MANTLE_URL_TEMPLATE = "https://bedrock-mantle.{region}.api.aws/v1/chat/completions"
# A full ~4000-token specification generation can genuinely take over a
# minute - 60s was observed timing out mid-generation ("read operation
# timed out") on real calls; 180s gives real generations room to finish
# while still bounding worst-case latency. Callers generating a much longer
# completion (e.g. a full spec for a 5-10 minute video) should pass a
# larger `timeout` explicitly - see bedrock_specification_generator.py's
# `_timeout_for_max_tokens()` - a live-verified 600s-duration request used
# ~16K completion tokens and took ~260s, well past this default.
_TIMEOUT_SECONDS = 180


def call_bedrock_chat(
    messages: list[dict],
    *,
    system: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.6,
    json_object: bool = False,
    timeout: float | None = None,
) -> str | None:
    """`messages` is OpenAI-style: `[{"role": "user"|"assistant", "content": "<str>"}, ...]`.

    `json_object=True` sets `response_format: {"type": "json_object"}` -
    live-verified supported by the Mantle gateway - which makes the model's
    own decoding guarantee syntactically valid JSON, instead of relying on
    prompt instructions alone. Callers that parse the reply as JSON should
    always pass this; it eliminates the "not valid JSON" failure mode that
    used to burn a full retry round trip for nothing.

    Returns the assistant's reply text, or None on any failure (no key
    configured, auth, network, malformed response) - every caller must have
    a deterministic fallback; a failed generation must never break video
    creation.
    """
    if not settings.bedrock_api_key:
        return None

    payload_messages = list(messages)
    if system:
        payload_messages = [{"role": "system", "content": system}] + payload_messages

    url = _MANTLE_URL_TEMPLATE.format(region=settings.bedrock_mantle_region)
    payload = {
        "model": settings.bedrock_model_id,
        "messages": payload_messages,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_object:
        payload["response_format"] = {"type": "json_object"}
    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.bedrock_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout if timeout is not None else _TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001 - Bedrock/network failures must never break video creation
        logger.error("bedrock_mantle_call_failed", error=str(exc))
        return None
