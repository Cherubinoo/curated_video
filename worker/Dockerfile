# DSA Video Studio - render worker image: Manim Community Edition + FFmpeg +
# the animation engine. Only this image ever invokes Manim; the API backend
# image (backend/Dockerfile) does not have it installed at all.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        python3-dev \
        libcairo2-dev \
        libpango1.0-dev \
        libjpeg-dev \
        zlib1g-dev \
        ffmpeg \
        fonts-dejavu-core \
        fontconfig \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Backend requirements files live at backend/requirements*.txt; the worker
# reuses the whole backend/ package (models, schemas, animation_engine) so
# there is exactly one source of truth for that code - see COPY below.
COPY backend/requirements.txt /app/requirements.txt
COPY backend/requirements-worker.txt /app/requirements-worker.txt
RUN pip install -r requirements-worker.txt

COPY backend/ /app/

RUN useradd -m -u 1000 renderer && chown -R renderer:renderer /app
USER renderer

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD celery -A app.core.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# One video at a time: concurrency=1 (product spec Section 10). Scaling to
# multiple simultaneous renders later is a deploy-config change
# (replicas / --concurrency), not a code change.
CMD ["celery", "-A", "app.core.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
