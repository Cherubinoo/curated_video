"""Celery application instance shared by the FastAPI backend (to enqueue
tasks) and the video-worker container (to consume them).

Only one worker/replica should run with a concurrency > 1 for now (see
Section 10 of the product spec: one Manim render at a time). That is
enforced operationally in docker-compose (`--concurrency=1`, one replica),
not in this module, so scaling later is a deploy-config change only.
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "dsa_video_studio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Hard ceiling slightly above our own render timeout so a stuck Manim
    # subprocess can't wedge the worker forever.
    task_time_limit=settings.render_timeout_seconds + 120,
    task_soft_time_limit=settings.render_timeout_seconds + 60,
)
