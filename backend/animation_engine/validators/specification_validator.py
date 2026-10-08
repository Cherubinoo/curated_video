"""Single entry point for turning raw JSON/dict into a trusted
VideoSpecification. Used by both the API (`/generate`) and the render
worker (which re-validates before every render - it never trusts the DB
blindly, per the product spec's security requirements).
"""
from __future__ import annotations

from pydantic import ValidationError

from app.schemas.specification import VideoSpecification


class SpecificationValidationResult:
    def __init__(self, specification: VideoSpecification | None, errors: list[str], warnings: list[str]):
        self.specification = specification
        self.errors = errors
        self.warnings = warnings

    @property
    def is_valid(self) -> bool:
        return self.specification is not None and not self.errors


def _format_pydantic_error(err: dict) -> str:
    loc = ".".join(str(part) for part in err["loc"])
    return f"{loc}: {err['msg']}" if loc else err["msg"]


def validate_specification(raw: dict) -> SpecificationValidationResult:
    """Parse + validate a raw dict against the VideoSpecification DSL.

    Never raises - all failures are collected into `.errors` so callers can
    persist them (VideoSpecification.validation_errors) and show them to the
    user without exposing a raw stack trace.
    """
    if not isinstance(raw, dict):
        return SpecificationValidationResult(None, ["specification must be a JSON object"], [])

    try:
        spec = VideoSpecification.model_validate(raw)
    except ValidationError as exc:
        errors = [_format_pydantic_error(e) for e in exc.errors()]
        return SpecificationValidationResult(None, errors, [])

    return SpecificationValidationResult(spec, [], spec.all_warnings())
