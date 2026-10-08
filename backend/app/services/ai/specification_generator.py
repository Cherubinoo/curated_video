"""Interface the future AI layer implements: natural language prompt in,
validated VideoSpecification out. Nothing downstream ever sees or executes
raw model output directly - `generate_specification` must always return
JSON that then goes through `validate_specification` before it is trusted.

`PlaceholderSpecGenerator` is the only implementation today. It does not
call any LLM; it deterministically returns the bundled demo specification
so `/api/videos/{id}/generate` is usable end to end right now, while making
it unmistakable (via logging and the returned metadata) that real prompt
understanding is future work (product spec Section 22, Phase 10).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.specification import VideoSpecification
from app.services.ai.demo_specification import build_demo_specification
from animation_engine.validators.specification_validator import validate_specification

logger = get_logger(__name__)


class SpecificationGenerationError(Exception):
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class VideoSpecificationGenerator(ABC):
    @abstractmethod
    def generate_specification(
        self, prompt: str, *, title: str, topic: str, duration_target: int
    ) -> VideoSpecification:
        """Turn a natural-language prompt into a validated VideoSpecification."""


class PlaceholderSpecGenerator(VideoSpecificationGenerator):
    """Deterministic placeholder: ignores the prompt's content and returns
    the bundled array+pointer demo spec, sized to the requested duration.
    Replace this with a real LLM-backed implementation in Phase 10 without
    changing any caller - they only depend on `VideoSpecificationGenerator`.
    """

    def generate_specification(
        self, prompt: str, *, title: str, topic: str, duration_target: int
    ) -> VideoSpecification:
        logger.warning(
            "placeholder_specification_generator_used",
            reason="No real AI VideoSpecificationGenerator is implemented yet (Phase 10 future work).",
            prompt_length=len(prompt),
        )
        raw = build_demo_specification(title=title, topic=topic, duration_target=duration_target)
        result = validate_specification(raw)
        if not result.is_valid:
            # Should never happen - this is our own bundled, tested spec.
            raise SpecificationGenerationError(
                "Placeholder specification failed validation (this is a bug).", errors=result.errors
            )
        return result.specification


def get_specification_generator() -> VideoSpecificationGenerator:
    if settings.bedrock_api_key:
        from app.services.ai.bedrock_specification_generator import BedrockSpecificationGenerator

        return BedrockSpecificationGenerator()
    return PlaceholderSpecGenerator()
