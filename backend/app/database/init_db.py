"""Database initialization and migration utilities."""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine, get_session_local
from app.database.models import (
    User,
    UserPreferences,
    WorkingHours,
    Appointment,
    AppointmentAttendee,
    Calendar,
    AvailabilityRule,
    ConversationSession,
    ConversationMessage,
    ExternalIntegration,
    AuditLog,
)


def init_db():
    """Initialize database - create tables if they don't exist."""
    # Create all tables
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def check_migration(migration_name: str, db_session: Session) -> bool:
    """Check if a migration has been applied."""
    # Simple migration tracking using a table
    try:
        # Try to check if migration table exists
        result = db_session.execute(
            text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'migrations'")
        ).scalar()
        if result == 0:
            # Create migrations table if it doesn't exist
            db_session.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL UNIQUE,
                        applied_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            )
            db_session.commit()
        # Check if this specific migration was applied
        result = db_session.execute(
            text(
                "SELECT COUNT(*) FROM migrations WHERE name = :name"
            ),
            {"name": migration_name},
        ).scalar()
        return result > 0
    except Exception:
        return False


def record_migration(migration_name: str, db_session: Session):
    """Record that a migration was applied."""
    db_session.execute(
        text(
            "INSERT INTO migrations (name, applied_at) VALUES (:name, NOW())"
        ),
        {"name": migration_name},
    )
    db_session.commit()