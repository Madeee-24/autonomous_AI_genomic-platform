"""
SQLAlchemy database engine, session factory, and dependency injection provider.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base

# Engine configuration with connection pooling and health checks
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    Rolls back uncommitted transactions on error and closes the session.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all_tables(target_engine=None) -> None:
    """
    Creates all defined tables in the connected database.
    Used for local initialization and automated test fixtures.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    logger.info("Database tables verified/created successfully.")

