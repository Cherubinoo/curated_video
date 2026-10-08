"""Test/dev convenience helpers. Production schema changes always go through
Alembic migrations (see backend/alembic/) - this module is only used by the
test suite to spin up a schema quickly against a throwaway database.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine

from app.models import Base


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def drop_all(engine: Engine) -> None:
    Base.metadata.drop_all(bind=engine)
