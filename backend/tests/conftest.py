"""Shared pytest fixtures.

DB-backed tests need a reachable Postgres (they use real JSONB/UUID
columns, so SQLite is not a substitute) - run them where `DATABASE_URL`
resolves, e.g. inside the `backend` container:

    docker compose exec backend pytest

Each `db_session` test runs inside a transaction that is rolled back
afterward, so tests never leave data behind or interfere with each other.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import settings
from app.db.init_db import create_all
from app.main import app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", settings.database_url)
_engine = create_engine(TEST_DATABASE_URL, future=True)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    create_all(_engine)
    yield


@pytest.fixture()
def db_session():
    """A session bound to one connection/transaction that is always rolled
    back at teardown. `join_transaction_mode="create_savepoint"` makes any
    `session.commit()` called by app code (routes/services commit freely)
    only release a SAVEPOINT, so the outer transaction - and the final
    rollback - stay intact and no test data ever leaks into the real DB."""
    connection = _engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection, future=True, join_transaction_mode="create_savepoint"
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> dict:
    return {"X-API-Key": settings.api_key}
