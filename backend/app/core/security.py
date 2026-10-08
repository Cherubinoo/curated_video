"""API-key authentication for admin endpoints.

This is a deliberately simple scheme for a single-admin internal tool: a
static key from settings, compared in constant time, sent as the `X-API-Key`
header. It is easy to swap for real per-user JWT auth later (the `User`
model already exists for that) without touching route handlers, since they
only depend on `require_api_key`.
"""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
