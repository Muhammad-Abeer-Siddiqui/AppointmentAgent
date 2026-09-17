"""Integration tests for the AI Appointment Scheduling Agent."""

import pytest
import uuid
from datetime import datetime, date, time, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db_session, engine, Base
from app.database.models import User, UserPreferences, WorkingHours, Appointment
from app.auth import create_access_token, get_password_hash
from app.scheduling.engine import generate_available_slots


# Test database setup
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user with unique email."""
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        name="Test User",
        email=unique_email,
        password_hash=get_password_hash("testpassword"),
        timezone="America/Toronto",
        locale="en",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Add default preferences
    prefs = UserPreferences(
        user_id=user.id,
        preferred_earliest_time=time(9, 0),
        preferred_latest_time=time(17, 0),
        avoid_lunch=True,
        min_break_minutes=30,
        preferred_duration_minutes=60,
    )
    db_session.add(prefs)

    # Add working hours (Mon-Fri 9-5)
    for day in range(5):
        wh = WorkingHours(
            user_id=user.id,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_off_day=False,
        )
        db_session.add(wh)

    db_session.commit()
    return user


@pytest.fixture
def auth_token(test_user):
    """Create an auth token for the test user."""
    return create_access_token(data={"sub": str(test_user.id)})


@pytest.fixture
async def async_client():
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as client:
        yield client


class TestAuth:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self, async_client):
        """Test user registration."""
        response = await async_client.post(
            "/auth/register",
            json={
                "email": f"newuser_{uuid.uuid4().hex[:8]}@example.com",
                "password": "password123",
                "name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client, test_user):
        """Test registration with duplicate email fails."""
        response = await async_client.post(
            "/auth/register",
            json={
                "email": test_user.email,
                "password": "password123",
                "name": "Another User",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_user(self, async_client, test_user):
        """Test user login."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, async_client, test_user):
        """Test login with invalid password fails."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me(self, async_client, auth_token, test_user):
        """Test getting current user profile."""
        response = await async_client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["name"] == "Test User"
        assert data["timezone"] == "America/Toronto"

    @pytest.mark.asyncio
    async def test_logout(self, async_client, auth_token):
        """Test user logout."""
        response = await async_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


class TestAgentEndpoints:
    """Test agent tool endpoints (direct tool calls)."""

    @pytest.mark.asyncio
    async def test_search_availability(self, async_client, auth_token, test_user):
        """Test search_availability agent endpoint."""
        response = await async_client.post(
            "/agent/search-availability",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "duration_minutes": 60,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "user_tz": "America/Toronto",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "slots" in data
        assert "duration_minutes" in data

    @pytest.mark.asyncio
    async def test_multi_person_availability(self, async_client, auth_token, test_user, db_session):
        """Test multi_person_availability agent endpoint."""
        # Create another user
        user2 = User(
            name="Test User 2",
            email=f"test2_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("testpassword"),
            timezone="America/Toronto",
            locale="en",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # Add working hours for user2
        for day in range(5):
            wh = WorkingHours(
                user_id=user2.id,
                day_of_week=day,
                start_time=time(10, 0),
                end_time=time(18, 0),
                is_off_day=False,
            )
            db_session.add(wh)
        db_session.commit()

        response = await async_client.post(
            "/agent/multi-person-availability",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "attendee_ids": [test_user.id, user2.id],
                "duration_minutes": 60,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "user_tz": "America/Toronto",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "slots" in data

    @pytest.mark.asyncio
    async def test_create_appointment_agent(self, async_client, auth_token, test_user):
        """Test create_appointment agent endpoint."""
        tomorrow = date.today() + timedelta(days=1)
        start_time = datetime.combine(tomorrow, time(10, 0)).isoformat()
        end_time = datetime.combine(tomorrow, time(11, 0)).isoformat()

        response = await async_client.post(
            "/agent/create-appointment",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Test Meeting",
                "description": "A test meeting",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Meeting"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_appointment_conflict(self, async_client, auth_token, test_user):
        """Test creating conflicting appointment fails."""
        tomorrow = date.today() + timedelta(days=1)
        start_time = datetime.combine(tomorrow, time(10, 0)).isoformat()
        end_time = datetime.combine(tomorrow, time(11, 0)).isoformat()

        # Create first appointment
        await async_client.post(
            "/agent/create-appointment",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "First Meeting",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )

        # Try to create overlapping appointment
        response = await async_client.post(
            "/agent/create-appointment",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Conflicting Meeting",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )
        assert response.status_code == 409


class TestChatAPI:
    """Test chat API endpoints (AI agent interaction)."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_basic(self, async_client, auth_token, test_user):
        """Test basic chat endpoint."""
        response = await async_client.post(
            "/agent/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "message": "Hello, what can you help me with?",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_chat_endpoint_with_tools(self, async_client, auth_token, test_user):
        """Test chat endpoint that triggers tool calls."""
        response = await async_client.post(
            "/agent/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "message": "Find me a 60-minute slot tomorrow morning",
            },
            timeout=30.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        # May have tool calls for search_availability
        if data.get("tool_calls"):
            tool_names = [tc["name"] for tc in data["tool_calls"]]
            assert "search_availability" in tool_names

    @pytest.mark.asyncio
    async def test_chat_suggestion(self, async_client, auth_token, test_user):
        """Test chat suggestion endpoint."""
        response = await async_client.post(
            "/agent/chat/suggestion",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestion" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_chat_clear_history(self, async_client, auth_token, test_user):
        """Test chat clear history endpoint."""
        response = await async_client.post(
            "/agent/chat/clear-history",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Conversation history cleared"


class TestAppointmentsCRUD:
    """Test appointments CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_appointment(self, async_client, auth_token, test_user):
        """Test creating appointment via REST API."""
        tomorrow = date.today() + timedelta(days=1)
        start_time = datetime.combine(tomorrow, time(10, 0)).isoformat()
        end_time = datetime.combine(tomorrow, time(11, 0)).isoformat()

        response = await async_client.post(
            "/appointments/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "REST API Meeting",
                "description": "Created via REST API",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "REST API Meeting"

    @pytest.mark.asyncio
    async def test_get_appointments(self, async_client, auth_token, test_user):
        """Test getting appointments list."""
        response = await async_client.get(
            "/appointments/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("appointments"), list)

    @pytest.mark.asyncio
    async def test_get_appointment(self, async_client, auth_token, test_user):
        """Test getting a single appointment."""
        tomorrow = date.today() + timedelta(days=1)
        start_time = datetime.combine(tomorrow, time(10, 0)).isoformat()
        end_time = datetime.combine(tomorrow, time(11, 0)).isoformat()

        # Create appointment
        create_response = await async_client.post(
            "/appointments/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Test Meeting",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )
        appointment_id = create_response.json()["id"]

        # Get appointment
        response = await async_client.get(
            f"/appointments/{appointment_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == appointment_id

    @pytest.mark.asyncio
    async def test_update_appointment(self, async_client, auth_token, test_user):
        """Test updating appointment."""
        tomorrow = date.today() + timedelta(days=1)
        start_time = datetime.combine(tomorrow, time(10, 0)).isoformat()
        end_time = datetime.combine(tomorrow, time(11, 0)).isoformat()

        # Create appointment
        create_response = await async_client.post(
            "/appointments/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Original Title",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )
        appointment_id = create_response.json()["id"]

        # Update appointment
        new_start = datetime.combine(tomorrow, time(14, 0)).isoformat()
        new_end = datetime.combine(tomorrow, time(15, 0)).isoformat()

        response = await async_client.patch(
            f"/appointments/{appointment_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Updated Title",
                "start_time": new_start,
                "end_time": new_end,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_appointment(self, async_client, auth_token, test_user):
        """Test deleting appointment."""
        tomorrow = date.today() + timedelta(days=1)
        start_time = datetime.combine(tomorrow, time(10, 0)).isoformat()
        end_time = datetime.combine(tomorrow, time(11, 0)).isoformat()

        # Create appointment
        create_response = await async_client.post(
            "/appointments/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "To Delete",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": 60,
            },
        )
        appointment_id = create_response.json()["id"]

        # Delete appointment
        response = await async_client.delete(
            f"/appointments/{appointment_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

        # Verify cancelled (soft delete - appointment still exists with cancelled status)
        get_response = await async_client.get(
            f"/appointments/{appointment_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "cancelled"


class TestCalendar:
    """Test calendar endpoints."""

    @pytest.mark.asyncio
    async def test_get_calendar(self, async_client, auth_token, test_user):
        """Test getting calendar."""
        response = await async_client.get(
            "/calendar/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data

    @pytest.mark.asyncio
    async def test_get_calendar_with_filters(self, async_client, auth_token, test_user):
        """Test getting calendar with date filters."""
        response = await async_client.get(
            "/calendar/",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data


class TestPreferences:
    """Test preferences endpoints."""

    @pytest.mark.asyncio
    async def test_get_preferences(self, async_client, auth_token, test_user):
        """Test getting user preferences."""
        response = await async_client.get(
            "/preferences/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "preferred_earliest_time" in data.get("preferences", {})
        assert "preferred_latest_time" in data.get("preferences", {})

    @pytest.mark.asyncio
    async def test_update_preferences(self, async_client, auth_token, test_user):
        """Test updating user preferences."""
        response = await async_client.patch(
            "/preferences/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "preferred_earliest_time": "08:00",
                "preferred_latest_time": "18:00",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preferred_earliest_time"] == "08:00"
        assert data["preferred_latest_time"] == "18:00"


class TestAvailability:
    """Test availability endpoints."""

    @pytest.mark.asyncio
    async def test_search_availability_endpoint(self, async_client, auth_token, test_user):
        """Test search availability REST endpoint."""
        response = await async_client.post(
            "/availability/search/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "duration_minutes": 30,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "slots" in data
        assert "slots" in data


class TestWorkingHours:
    """Test working hours endpoints."""

    @pytest.mark.asyncio
    async def test_get_working_hours(self, async_client, auth_token, test_user):
        """Test getting working hours."""
        response = await async_client.get(
            "/users/working-hours/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_update_working_hours(self, async_client, auth_token, test_user):
        """Test updating working hours."""
        response = await async_client.patch(
            "/users/working-hours/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "working_hours": [
                    {"day_of_week": 0, "start_time": "09:00", "end_time": "17:00", "is_off_day": False},
                    {"day_of_week": 1, "start_time": "09:00", "end_time": "17:00", "is_off_day": False},
                    {"day_of_week": 2, "start_time": "09:00", "end_time": "17:00", "is_off_day": False},
                    {"day_of_week": 3, "start_time": "09:00", "end_time": "17:00", "is_off_day": False},
                    {"day_of_week": 4, "start_time": "09:00", "end_time": "17:00", "is_off_day": False},
                    {"day_of_week": 5, "start_time": "09:00", "end_time": "12:00", "is_off_day": True},
                    {"day_of_week": 6, "start_time": "09:00", "end_time": "12:00", "is_off_day": True},
                ]
            },
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
