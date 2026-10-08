"""Convenience launcher for running the render worker outside Docker (e.g.
local development without containers). The `video-worker` Docker image
invokes the Celery CLI directly (see worker/Dockerfile's CMD); this script
does the same thing so `python worker/render_worker.py` works identically
from a plain virtualenv that has backend/requirements-worker.txt installed
and backend/ on PYTHONPATH.

Usage:
    cd backend && python ../worker/render_worker.py
"""
from __future__ import annotations

import sys

from app.core.celery_app import celery_app

if __name__ == "__main__":
    argv = ["worker", "--loglevel=info", "--concurrency=1"]
    celery_app.worker_main(argv=[sys.argv[0]] + argv)
