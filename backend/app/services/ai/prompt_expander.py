"""Turns a short (topic, description) pair from the New Video form into a
detailed educational video generation prompt - a distinct, earlier step
from `VideoSpecificationGenerator`. This only ever produces plain text (the
detailed prompt); that text is then reviewable/editable in the frontend and,
once the admin proceeds, stored as `Video.prompt` and fed through the
normal `/generate` flow completely unchanged - no new trust boundary is
introduced, it's still just text in, validated spec out.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.bedrock_client import call_bedrock_chat

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an assistant that writes detailed educational video generation prompts for "
    "short (1-2.5 minute) programming/DSA concept videos. Given a topic and a short "
    "description from the admin, write ONE detailed prompt (roughly 150-400 words) that a "
    "video generation pipeline can use. Cover: what the student should learn, the key "
    "concept(s) to visualize, a suggested narration flow/structure, and the desired tone "
    "and pacing. Respond with ONLY the prompt text itself - no markdown headers, no code "
    "fences, no preamble like \"Here is...\", no commentary before or after."
)


class PromptExpander(ABC):
    @abstractmethod
    def expand(self, topic: str, description: str) -> str:
        """Turn a short topic + description into a detailed prompt string."""


class PlaceholderPromptExpander(PromptExpander):
    """No AI configured (or a call failed) - deterministically build a
    reasonable prompt from the inputs so this step never blocks the flow."""

    def expand(self, topic: str, description: str) -> str:
        return (
            f'Create a short (1-2.5 minute) educational programming concept video about '
            f'"{topic}".\n\n'
            f"Description from the admin: {description}\n\n"
            "Explain the core idea clearly with a simple, concrete visual example. "
            "Narrate the key steps as they happen on screen, define any important terms "
            "the first time they appear, and keep the pacing brisk and beginner-friendly "
            "throughout."
        )


class BedrockPromptExpander(PromptExpander):
    """Reuses the same low-cost Bedrock model as narration generation (see
    `bedrock_specification_generator.py`) via the shared Mantle client
    (`app.services.ai.bedrock_client`)."""

    def expand(self, topic: str, description: str) -> str:
        user_message = f"Topic: {topic}\nShort description from the admin: {description}"
        text = call_bedrock_chat(
            [{"role": "user", "content": user_message}],
            system=_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.7,
        )
        if text and text.strip():
            return text.strip()
        if text is not None:
            logger.warning("bedrock_prompt_expansion_empty_response")

        return PlaceholderPromptExpander().expand(topic, description)


def get_prompt_expander() -> PromptExpander:
    if settings.bedrock_api_key:
        return BedrockPromptExpander()
    return PlaceholderPromptExpander()
