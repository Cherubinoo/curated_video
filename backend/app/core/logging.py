"""Structured logging setup.

Uses structlog with a JSON renderer in production-like environments and a
console renderer for local development. Call `configure_logging()` once at
process startup (FastAPI app startup and Celery worker startup both do this).

Use `bind_job_context(job_id=..., video_id=..., stage=..., worker_id=...)` to
attach the fields the spec asks us to track to every subsequent log line in
that context.
"""
from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.environment != "development"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)


def bind_job_context(**kwargs) -> None:
    """Bind fields (job_id, video_id, stage, worker_id, ...) to all subsequent
    log lines emitted on this thread/task until `clear_job_context()` is called.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_job_context() -> None:
    structlog.contextvars.clear_contextvars()
