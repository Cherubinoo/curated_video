"""Shared slowapi Limiter instance for mutating endpoints (create/generate/
regenerate). Simple in-process rate limiting is enough for a single-admin
internal tool; swap for a Redis-backed limiter if this ever needs to scale
across multiple backend replicas."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
