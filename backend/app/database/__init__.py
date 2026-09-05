"""Database module for the AI Appointment Scheduling Agent."""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from app.core.config import settings

# Synchronous engine (used for all DB operations)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Global metadata for reflections, etc.
metadata = MetaData()


def get_engine():
    """Get synchronous engine."""
    return engine


def get_session_local():
    """Get sync session local."""
    return SessionLocal


def get_db_session():
    """Dependency to get a synchronous DB session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
