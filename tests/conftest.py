"""
Shared fixtures and configuration for pytest.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from app.db import session
from app.db.models import Base


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """
    Autouse fixture that patches the application's database session
    to use an in-memory SQLite database for test isolation.
    """
    # Create in-memory engine with a StaticPool to persist connection
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)

    # Session maker for the memory DB
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    # Patch the engine and SessionLocal in app.db.session module
    monkeypatch.setattr(session, "engine", test_engine)
    monkeypatch.setattr(session, "SessionLocal", TestSessionLocal)

    yield

    # Clean up
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
