"""Shared test fixtures: in-memory SQLite engine and session.

``create_all`` is allowed here only — production schema is managed
exclusively by Alembic migrations.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from crossdock.storage.database import build_engine
from crossdock.storage.tables import Base


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.rollback()
    session.close()
