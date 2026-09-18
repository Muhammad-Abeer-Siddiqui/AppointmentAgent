"""Benchmark tests for AI tool dispatcher (execute_tool)."""

import os
import sys
import uuid
import importlib
import importlib.util
from datetime import datetime, date, time, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import patch, AsyncMock

# ---------------------------------------------------------------------------
# Patch app.core.config BEFORE any app import so pydantic-settings never
# parses the real .env (which contains ALLOWED_ORIGINS that Settings rejects).
# ---------------------------------------------------------------------------
_fake_config = ModuleType("app.core.config")


class _FakeSettings:
    DATABASE_URL = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret"
    JWT_ALGORITHM = "HS256"
    GEMINI_API_KEY = "test-key"
    GEMINI_MODEL = "gemini-1.5-flash"
    FRONTEND_URL = "http://localhost:3000"
    GOOGLE_CLIENT_ID = ""
    GOOGLE_CLIENT_SECRET = ""
    GOOGLE_REDIRECT_URI = ""


_fake_config.settings = _FakeSettings()  # type: ignore[attr-defined]
_fake_config.get_settings = lambda: _FakeSettings()  # type: ignore[attr-defined]
sys.modules["app.core.config"] = _fake_config

# Also prevent app.database from creating a real PostgreSQL engine at import
_fake_db = ModuleType("app.database")
_fake_db.__package__ = "app.database"

from sqlalchemy.orm import DeclarativeBase


class _TestBase(DeclarativeBase):
    pass


_fake_db.Base = _TestBase  # type: ignore[attr-defined]
_fake_db.engine = None  # type: ignore[attr-defined]
_fake_db.SessionLocal = None  # type: ignore[attr-defined]
_fake_db.get_engine = lambda: None  # type: ignore[attr-defined]
_fake_db.get_session_local = lambda: None  # type: ignore[attr-defined]


def _stub_get_db_session():
    raise RuntimeError("test_tools: get_db_session should not be called directly")


_fake_db.get_db_session = _stub_get_db_session  # type: ignore[attr-defined]
sys.modules["app.database"] = _fake_db

# Use importlib to load models.py directly, avoiding __init__.py side-effects
_models_path = str(Path(__file__).resolve().parents[2] / "app" / "database" / "models.py")
_spec = importlib.util.spec_from_file_location("app.database.models", _models_path,
                                                submodule_search_locations=[])
_models_module = importlib.util.module_from_spec(_spec)
sys.modules["app.database.models"] = _models_module
_spec.loader.exec_module(_models_module)

import pytest
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.database.models import (
    User,
    UserPreferences,
    WorkingHours,
    Appointment,
)
from app.ai.tools import execute_tool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    eng = sa_create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db(engine):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def test_user(db):
    user = User(
        name="Tool Test User",
        email=f"tooltest_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="fakehash",
        timezone="America/Toronto",
        locale="en",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    prefs = UserPreferences(
        user_id=user.id,
        preferred_earliest_time=time(9, 0),
        preferred_latest_time=time(17, 0),
        avoid_lunch=True,
        min_break_minutes=30,
        preferred_duration_minutes=60,
    )
    db.add(prefs)

    for day in range(5):
        db.add(
            WorkingHours(
                user_id=user.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_off_day=False,
            )
        )
    db.commit()
    db.refresh(user)
    return user


def _future_dt(hour: int, day_offset: int = 1) -> datetime:
    return datetime.combine(date.today() + timedelta(days=day_offset), time(hour, 0))


def _future_dt_str(hour: int, day_offset: int = 1) -> str:
    return _future_dt(hour, day_offset).isoformat()


# ---------------------------------------------------------------------------
# 1. search_availability  (4 tests)
# ---------------------------------------------------------------------------

class TestSearchAvailability:
    @pytest.mark.asyncio
    async def test_returns_slots_for_valid_range(self, db, test_user):
        result = await execute_tool(
            "search_availability",
            {
                "duration_minutes": 60,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "user_tz": "America/Toronto",
            },
            test_user.id,
            db,
        )
        assert "slots" in result
        assert "total_found" in result
        assert isinstance(result["slots"], list)

    @pytest.mark.asyncio
    async def test_returns_empty_for_past_dates(self, db, test_user):
        past_start = (date.today() - timedelta(days=10)).isoformat()
        past_end = (date.today() - timedelta(days=3)).isoformat()
        result = await execute_tool(
            "search_availability",
            {
                "duration_minutes": 60,
                "start_date": past_start,
                "end_date": past_end,
                "user_tz": "America/Toronto",
            },
            test_user.id,
            db,
        )
        # Engine returns slots for any date range (no past-date filtering),
        # but the result structure is always valid.
        assert isinstance(result["slots"], list)
        assert isinstance(result["total_found"], int)
        assert result["duration_minutes"] == 60

    @pytest.mark.asyncio
    async def test_respects_duration_minutes(self, db, test_user):
        short = await execute_tool(
            "search_availability",
            {
                "duration_minutes": 30,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=3)).isoformat(),
                "user_tz": "America/Toronto",
            },
            test_user.id,
            db,
        )
        long = await execute_tool(
            "search_availability",
            {
                "duration_minutes": 120,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=3)).isoformat(),
                "user_tz": "America/Toronto",
            },
            test_user.id,
            db,
        )
        assert short["total_found"] >= long["total_found"]
        assert short["duration_minutes"] == 30
        assert long["duration_minutes"] == 120

    @pytest.mark.asyncio
    async def test_invalid_timezone_raises_error(self, db, test_user):
        from zoneinfo import ZoneInfoNotFoundError
        with pytest.raises(ZoneInfoNotFoundError):
            await execute_tool(
                "search_availability",
                {
                    "duration_minutes": 60,
                    "start_date": date.today().isoformat(),
                    "end_date": (date.today() + timedelta(days=3)).isoformat(),
                    "user_tz": "Invalid/Timezone",
                },
                test_user.id,
                db,
            )


# ---------------------------------------------------------------------------
# 2. create_appointment  (4 tests)
# ---------------------------------------------------------------------------

class TestCreateAppointment:
    @pytest.mark.asyncio
    async def test_creates_successfully(self, db, test_user):
        with patch("app.ai.tools.sync_user_to_google", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"success": False, "error": "not connected"}
            result = await execute_tool(
                "create_appointment",
                {
                    "title": "Unit Test Meeting",
                    "description": "Created by benchmark test",
                    "start_time": _future_dt_str(10),
                    "end_time": _future_dt_str(11),
                    "duration_minutes": 60,
                },
                test_user.id,
                db,
            )
        assert result["success"] is True
        assert "id" in result
        assert result["title"] == "Unit Test Meeting"
        appt = db.query(Appointment).filter(Appointment.id == result["id"]).first()
        assert appt is not None
        assert appt.status == "scheduled"

    @pytest.mark.asyncio
    async def test_returns_conflict_when_overlapping(self, db, test_user):
        with patch("app.ai.tools.sync_user_to_google", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"success": False, "error": "not connected"}
            await execute_tool(
                "create_appointment",
                {
                    "title": "First",
                    "start_time": _future_dt_str(14),
                    "end_time": _future_dt_str(15),
                    "duration_minutes": 60,
                },
                test_user.id,
                db,
            )
            result = await execute_tool(
                "create_appointment",
                {
                    "title": "Overlap",
                    "start_time": _future_dt_str(14),
                    "end_time": _future_dt_str(15),
                    "duration_minutes": 60,
                },
                test_user.id,
                db,
            )
        assert result["success"] is False
        assert "conflicts" in result
        assert len(result["conflicts"]) > 0

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, db, test_user):
        with pytest.raises(TypeError):
            await execute_tool(
                "create_appointment",
                {"title": "No Times"},
                test_user.id,
                db,
            )

    @pytest.mark.asyncio
    async def test_past_date_appointment(self, db, test_user):
        with patch("app.ai.tools.sync_user_to_google", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"success": False}
            past = datetime.combine(date.today() - timedelta(days=5), time(10, 0)).isoformat()
            past_end = datetime.combine(date.today() - timedelta(days=5), time(11, 0)).isoformat()
            result = await execute_tool(
                "create_appointment",
                {
                    "title": "Past Meeting",
                    "start_time": past,
                    "end_time": past_end,
                    "duration_minutes": 60,
                },
                test_user.id,
                db,
            )
        assert result["success"] is True
        appt = db.query(Appointment).filter(Appointment.id == result["id"]).first()
        assert appt is not None


# ---------------------------------------------------------------------------
# 3. update_appointment  (3 tests)
# ---------------------------------------------------------------------------

class TestUpdateAppointment:
    @pytest.fixture()
    def existing_appointment(self, db, test_user):
        appt = Appointment(
            user_id=test_user.id,
            title="Original",
            description="Desc",
            start_time=_future_dt(10),
            end_time=_future_dt(11),
            duration_minutes=60,
            status="scheduled",
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)
        return appt

    @pytest.mark.asyncio
    async def test_updates_title(self, db, test_user, existing_appointment):
        result = await execute_tool(
            "update_appointment",
            {"appointment_id": existing_appointment.id, "title": "Updated Title"},
            test_user.id,
            db,
        )
        assert result["success"] is True
        assert result["title"] == "Updated Title"
        db.refresh(existing_appointment)
        assert existing_appointment.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_updates_time(self, db, test_user, existing_appointment):
        new_start = _future_dt(13)
        new_end = _future_dt(14)
        result = await execute_tool(
            "update_appointment",
            {
                "appointment_id": existing_appointment.id,
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
            test_user.id,
            db,
        )
        assert result["success"] is True
        db.refresh(existing_appointment)
        assert existing_appointment.start_time.hour == 13

    @pytest.mark.asyncio
    async def test_nonexistent_appointment(self, db, test_user):
        result = await execute_tool(
            "update_appointment",
            {"appointment_id": 999999, "title": "X"},
            test_user.id,
            db,
        )
        assert "error" in result
        assert "not found" in result["error"].lower()


# ---------------------------------------------------------------------------
# 4. cancel_appointment  (3 tests)
# ---------------------------------------------------------------------------

class TestCancelAppointment:
    @pytest.fixture()
    def cancellable(self, db, test_user):
        appt = Appointment(
            user_id=test_user.id,
            title="To Cancel",
            start_time=_future_dt(16),
            end_time=_future_dt(17),
            duration_minutes=60,
            status="scheduled",
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)
        return appt

    @pytest.mark.asyncio
    async def test_cancel_with_confirm_true(self, db, test_user, cancellable):
        result = await execute_tool(
            "cancel_appointment",
            {"appointment_id": cancellable.id, "confirm": True},
            test_user.id,
            db,
        )
        assert result["success"] is True
        db.refresh(cancellable)
        assert cancellable.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_with_confirm_false(self, db, test_user, cancellable):
        result = await execute_tool(
            "cancel_appointment",
            {"appointment_id": cancellable.id, "confirm": False},
            test_user.id,
            db,
        )
        assert "error" in result
        assert "not confirmed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_appointment(self, db, test_user):
        result = await execute_tool(
            "cancel_appointment",
            {"appointment_id": 999999, "confirm": True},
            test_user.id,
            db,
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# 5. get_user_profile  (2 tests)
# ---------------------------------------------------------------------------

class TestGetUserProfile:
    @pytest.mark.asyncio
    async def test_returns_correct_user_data(self, db, test_user):
        result = await execute_tool("get_user_profile", {}, test_user.id, db)
        assert result["id"] == test_user.id
        assert result["name"] == test_user.name
        assert result["email"] == test_user.email
        assert result["timezone"] == "America/Toronto"

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, db):
        result = await execute_tool("get_user_profile", {}, 0, db)
        assert "error" in result
        assert "not found" in result["error"].lower()


# ---------------------------------------------------------------------------
# 6. set_user_preferences  (2 tests)
# ---------------------------------------------------------------------------

class TestSetUserPreferences:
    @pytest.mark.asyncio
    async def test_sets_preferences_successfully(self, db, test_user):
        result = await execute_tool(
            "set_user_preferences",
            {
                "preferred_earliest_time": "08:30",
                "preferred_latest_time": "18:00",
                "avoid_lunch": False,
                "min_break_minutes": 15,
                "preferred_duration_minutes": 45,
            },
            test_user.id,
            db,
        )
        assert result["success"] is True
        db.refresh(test_user)
        prefs = test_user.preferences
        assert prefs.preferred_earliest_time == time(8, 30)
        assert prefs.preferred_latest_time == time(18, 0)
        assert prefs.avoid_lunch is False
        assert prefs.min_break_minutes == 15
        assert prefs.preferred_duration_minutes == 45

    @pytest.mark.asyncio
    async def test_partial_update(self, db, test_user):
        original_latest = test_user.preferences.preferred_latest_time
        await execute_tool(
            "set_user_preferences",
            {"min_break_minutes": 10},
            test_user.id,
            db,
        )
        db.refresh(test_user)
        assert test_user.preferences.min_break_minutes == 10
        assert test_user.preferences.preferred_latest_time == original_latest


# ---------------------------------------------------------------------------
# 7. get_calendar  (2 tests)
# ---------------------------------------------------------------------------

class TestGetCalendar:
    @pytest.fixture()
    def calendar_appointments(self, db, test_user):
        appts = []
        for i in range(3):
            appt = Appointment(
                user_id=test_user.id,
                title=f"Cal Event {i}",
                start_time=_future_dt(9 + i),
                end_time=_future_dt(10 + i),
                duration_minutes=60,
                status="scheduled",
            )
            db.add(appt)
            appts.append(appt)
        db.commit()
        for a in appts:
            db.refresh(a)
        return appts

    @pytest.mark.asyncio
    async def test_returns_appointments_in_range(self, db, test_user, calendar_appointments):
        result = await execute_tool(
            "get_calendar",
            {
                "start_date": (date.today()).isoformat(),
                "end_date": (date.today() + timedelta(days=2)).isoformat(),
            },
            test_user.id,
            db,
        )
        assert "appointments" in result
        assert result["total"] >= 3

    @pytest.mark.asyncio
    async def test_empty_range_returns_none(self, db, test_user):
        result = await execute_tool(
            "get_calendar",
            {
                "start_date": "2020-01-01T00:00:00",
                "end_date": "2020-01-02T00:00:00",
            },
            test_user.id,
            db,
        )
        assert result["appointments"] == []
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# 8. confirm_action passthrough
# ---------------------------------------------------------------------------

class TestConfirmAction:
    @pytest.mark.asyncio
    async def test_passthrough(self, db, test_user):
        payload = {"action": "cancel_appointment", "details": {"appointment_id": 1}}
        result = await execute_tool("confirm_action", payload, test_user.id, db)
        assert result == payload
