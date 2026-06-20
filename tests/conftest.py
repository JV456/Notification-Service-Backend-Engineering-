import os

# Must be set before any `app.*` module is imported, since app.config reads
# these env vars exactly once at import time.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["QUEUE_BACKEND"] = "memory"
os.environ["RATE_LIMIT_PER_HOUR"] = "100"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.queue.factory import reset_queue_for_tests
from app.services.rate_limiter import reset_rate_limiter_for_tests

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Fresh schema and fresh in-memory queue/rate-limiter state for every test."""
    Base.metadata.create_all(bind=engine)
    reset_queue_for_tests()
    reset_rate_limiter_for_tests()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)
