"""
Pytest global configuration and fixtures.
Configures an in-memory SQLite database with StaticPool for rapid, isolated test execution
without requiring an external PostgreSQL daemon.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.analysis_service import analysis_service

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Session-wide fixture that initializes an in-memory SQLite database,
    overrides the FastAPI get_db dependency, and injects the test session factory
    into background workers.
    """
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    analysis_service.session_factory = TestingSessionLocal

    yield test_engine

    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()

