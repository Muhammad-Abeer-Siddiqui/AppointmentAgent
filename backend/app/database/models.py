"""Database models for the AI Appointment Scheduling Agent."""

from datetime import datetime, date, time as dt_time
from typing import List, Dict, Optional, Tuple, Any

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    Boolean,
    Time,
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    TypeDecorator,
    types as sqltypes,
)
from sqlalchemy.sql.sqltypes import Time as DateTimeTime
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    Relationship,
    relationship,
)

from app.database import Base


# JSONB type decorator for SQLAlchemy 2.0 compatibility
class JSONB(TypeDecorator):
    """JSONB type for SQLAlchemy 2.0 - stores JSON in TEXT column."""
    impl = sqltypes.Text

    def process_bind_param(self, value, dialect):
        import json
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value, dialect):
        import json
        return json.loads(value) if value is not None else None


# =============================================================================
# USERS
# =============================================================================

class User(Base):
    """User model with authentication and profile data."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    preferences: Mapped["UserPreferences"] = relationship(
        "UserPreferences", back_populates="user", cascade="all, delete-orphan"
    )
    working_hours: Mapped[List["WorkingHours"]] = relationship(
        "WorkingHours", back_populates="user", cascade="all, delete-orphan"
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment", back_populates="owner", cascade="all, delete-orphan"
    )
    appointment_attendees: Mapped[List["AppointmentAttendee"]] = relationship(
        "AppointmentAttendee", back_populates="user", cascade="all, delete-orphan"
    )
    calendars: Mapped[List["Calendar"]] = relationship(
        "Calendar", back_populates="user", cascade="all, delete-orphan"
    )
    availability_rules: Mapped[List["AvailabilityRule"]] = relationship(
        "AvailabilityRule", back_populates="user", cascade="all, delete-orphan"
    )
    conversation_sessions: Mapped[List["ConversationSession"]] = relationship(
        "ConversationSession", back_populates="user", cascade="all, delete-orphan"
    )
    external_integrations: Mapped[List["ExternalIntegration"]] = relationship(
        "ExternalIntegration", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )


# =============================================================================
# USER PREFERENCES
# =============================================================================

class UserPreferences(Base):
    """User scheduling preferences."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Basic preferences
    preferred_earliest_time: Mapped[dt_time] = mapped_column(
        DateTimeTime, nullable=False, default=lambda: dt_time(9, 0)
    )
    preferred_latest_time: Mapped[dt_time] = mapped_column(
        DateTimeTime, nullable=False, default=lambda: dt_time(17, 0)
    )
    avoid_lunch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    preferred_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )

    # Derived / computed
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="preferences")


# =============================================================================
# WORKING HOURS
# =============================================================================

class WorkingHours(Base):
    """User working hours per day of week."""

    __tablename__ = "working_hours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 0=Monday, 6=Sunday (Python convention)
    start_time: Mapped[dt_time] = mapped_column(DateTimeTime, nullable=False)
    end_time: Mapped[dt_time] = mapped_column(DateTimeTime, nullable=False)
    is_off_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "start_time < end_time",
            name="chk_wh_start_before_end",
        ),
        Index("ix_wh_user_day", "user_id", "day_of_week"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="working_hours")


# =============================================================================
# APPOINTMENTS
# =============================================================================

class Appointment(Base):
    """Appointment model representing a scheduled appointment."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )  # scheduled, confirmed, cancelled, completed

    # Recurrence fields
    recurrence_rule: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # "daily", "weekly", "monthly" or NULL for one-time
    series_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )  # UUID linking all occurrences in a recurring series
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )  # Points to the first appointment in a series

    # Google Calendar sync fields
    google_calendar_event_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="appointments")
    attendees: Mapped[List["AppointmentAttendee"]] = relationship(
        "AppointmentAttendee", back_populates="appointment", cascade="all, delete-orphan"
    )


# =============================================================================
# APPOINTMENT ATTENDEES
# =============================================================================

class AppointmentAttendee(Base):
    """Appointment attendee model for multi-person scheduling."""

    __tablename__ = "appointment_attendees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Constraints
    __table_args__ = (
        Index("ix_aa_appointment", "appointment_id"),
        Index("ix_aa_email", "email"),
    )

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="attendees"
    )
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="appointment_attendees"
    )


# =============================================================================
# CALENDARS
# =============================================================================

class Calendar(Base):
    """User calendar integration model."""

    __tablename__ = "calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    external_calendar_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    calendar_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="calendars")


# =============================================================================
# AVAILABILITY RULES
# =============================================================================

class AvailabilityRule(Base):
    """Custom availability rules for the user."""

    __tablename__ = "availability_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recurrence_pattern: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="availability_rules")


# =============================================================================
# CONVERSATION SESSIONS
# =============================================================================

class ConversationSession(Base):
    """Conversation session for maintaining context."""

    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversation_sessions")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage", back_populates="session", cascade="all, delete-orphan"
    )


# =============================================================================
# CONVERSATION MESSAGES
# =============================================================================

class ConversationMessage(Base):
    """Individual message in a conversation session."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession", back_populates="messages"
    )


# =============================================================================
# EXTERNAL INTEGRATIONS
# =============================================================================

class ExternalIntegration(Base):
    """External API integration configuration."""

    __tablename__ = "external_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'gemini', 'weather', 'holiday', etc.
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="external_integrations")


# =============================================================================
# AUDIT LOGS
# =============================================================================

class AuditLog(Base):
    """Audit log for tracking actions and events."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    # Constraints
    __table_args__ = (
        Index("ix_al_user_created", "user_id", "created_at"),
        Index("ix_al_action_created", "action", "created_at"),
    )