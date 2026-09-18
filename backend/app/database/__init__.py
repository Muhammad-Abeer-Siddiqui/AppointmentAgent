"""Database module for the AI Appointment Scheduling Agent."""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from functools import lru_cache

from app.core.config import settings

# Synchronous engine with optimized pool settings for serverless (Supabase pooler)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=300,
    echo=False,
)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Global metadata for reflections, etc.
metadata = MetaData()

# ---------------------------------------------------------------------------
# In-memory LRU caches for frequently-accessed, rarely-changing data
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _cached_working_hours(user_id: int) -> tuple:
    """Cache working hours for a user (keyed by user_id).

    The cache is invalidated when the app process restarts, which is
    acceptable for a free-tier deployment. For production, use Redis.
    """
    db = SessionLocal()
    try:
        from app.database.models import WorkingHours
        rows = db.query(WorkingHours).filter(
            WorkingHours.user_id == user_id
        ).all()
        return tuple(
            {
                "day_of_week": r.day_of_week,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "is_off_day": r.is_off_day,
            }
            for r in rows
        )
    finally:
        db.close()


def invalidate_working_hours_cache(user_id: int) -> None:
    """Call this when a user's working hours are updated."""
    _cached_working_hours.cache_clear()


def get_working_hours(user_id: int) -> list[dict]:
    """Get working hours for a user, with in-memory caching."""
    return list(_cached_working_hours(user_id))


@lru_cache(maxsize=256)
def _cached_preferences(user_id: int) -> dict | None:
    """Cache user preferences."""
    db = SessionLocal()
    try:
        from app.database.models import UserPreferences
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        if not prefs:
            return None
        return {
            "preferred_earliest": prefs.preferred_earliest_time.strftime("%H:%M") if prefs.preferred_earliest_time else "09:00",
            "preferred_latest": prefs.preferred_latest_time.strftime("%H:%M") if prefs.preferred_latest_time else "17:00",
            "avoid_lunch": prefs.avoid_lunch,
            "min_break_minutes": prefs.min_break_minutes,
        }
    finally:
        db.close()


def invalidate_preferences_cache(user_id: int) -> None:
    """Call this when a user's preferences are updated."""
    _cached_preferences.cache_clear()


def get_preferences(user_id: int) -> dict:
    """Get user preferences with in-memory caching. Returns empty dict if none."""
    return _cached_preferences(user_id) or {}


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
