"""Domain-level exceptions raised by services, translated to HTTP errors at
the API layer (see app/api/routes) rather than leaking implementation
details (stack traces, ORM errors) to clients."""
from __future__ import annotations

import uuid


class VideoNotFoundError(Exception):
    def __init__(self, video_id: uuid.UUID):
        super().__init__(f"Video {video_id} not found")
        self.video_id = video_id


class RenderJobNotFoundError(Exception):
    def __init__(self, job_id: uuid.UUID):
        super().__init__(f"Render job {job_id} not found")
        self.job_id = job_id


class VideoActiveError(Exception):
    """Raised when an operation (e.g. delete) is attempted on a video that
    has a render currently queued or in progress."""

    def __init__(self, video_id: uuid.UUID):
        super().__init__(f"Video {video_id} is queued or processing")
        self.video_id = video_id
