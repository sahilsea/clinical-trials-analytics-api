"""Test setup.

Tests run against in-memory SQLite by default. Set TEST_DATABASE_URL to run the
same suite against PostgreSQL (CI does this).
"""

import os
from pathlib import Path

# Must happen before the app is imported, because the engine is created at import time.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or "sqlite://"
os.environ["API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from etl.pipeline import run_pipeline  # noqa: E402

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_trials.csv"
API_KEY_HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def seeded_db(db):
    """A database loaded with the fixture CSV through the real ETL pipeline."""
    run_pipeline(db, FIXTURE_CSV)
    return db


@pytest.fixture()
def client(seeded_db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth():
    return API_KEY_HEADERS
