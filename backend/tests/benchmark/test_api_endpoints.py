"""API contract tests for all endpoints.

Async integration tests verifying HTTP status codes, response shapes,
and business logic contracts for auth, users, appointments, agent,
calendar, availability, and preferences endpoints.
"""

import pytest
import uuid
from datetime import datetime, date, time as dt_time, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db_session, engine, Base, SessionLocal
from app.database.models import User, UserPreferences, WorkingHours, Appointment
from app.auth import create_access_token, create_refresh_token, get_password_hash


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create and tear down test database tables once per session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a isolated database session per test."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user with unique email, preferences, and working hours."""
    unique_email = f"bench_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        name="Bench User",
        email=unique_email,
        password_hash=get_password_hash("benchpass123"),
        timezone="America/Toronto",
        locale="en",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    prefs = UserPreferences(
        user_id=user.id,
        preferred_earliest_time=dt_time(9, 0),
        preferred_latest_time=dt_time(17, 0),
        avoid_lunch=True,
        min_break_minutes=30,
        preferred_duration_minutes=60,
    )
    db_session.add(prefs)

    for day in range(5):
        db_session.add(
            WorkingHours(
                user_id=user.id,
                day_of_week=day,
                start_time=dt_time(9, 0),
                end_time=dt_time(17, 0),
                is_off_day=False,
            )
        )

    db_session.commit()
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    """JWT access token for test_user."""
    return create_access_token(data={"sub": str(test_user.id)})


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Authorization headers dict."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def second_user(db_session: Session) -> User:
    """A second test user for multi-person tests."""
    user = User(
        name="Second User",
        email=f"second_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("pass123"),
        timezone="America/New_York",
        locale="en",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(
        UserPreferences(
            user_id=user.id,
            preferred_earliest_time=dt_time(10, 0),
            preferred_latest_time=dt_time(18, 0),
            avoid_lunch=True,
            min_break_minutes=30,
            preferred_duration_minutes=60,
        )
    )
    for day in range(5):
        db_session.add(
            WorkingHours(
                user_id=user.id,
                day_of_week=day,
                start_time=dt_time(10, 0),
                end_time=dt_time(18, 0),
                is_off_day=False,
            )
        )
    db_session.commit()
    return user


@pytest.fixture
async def async_client():
    """Async HTTP client wired to the FastAPI app via ASGITransport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=True,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# 1. Auth Endpoints (5 tests)
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    """POST /auth/register, POST /auth/login, POST /auth/refresh."""

    @pytest.mark.asyncio
    async def test_register_returns_201(self, async_client: AsyncClient):
        """POST /auth/register — 201 with valid data."""
        email = f"reg_{uuid.uuid4().hex[:8]}@example.com"
        resp = await async_client.post(
            "/auth/register",
            json={"name": "New User", "email": email, "password": "securepass"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == email
        assert body["user"]["name"] == "New User"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_400(
        self, async_client: AsyncClient, test_user: User
    ):
        """POST /auth/register — 400 when email already exists."""
        resp = await async_client.post(
            "/auth/register",
            json={
                "name": "Duplicate",
                "email": test_user.email,
                "password": "pass",
            },
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_returns_200(
        self, async_client: AsyncClient, test_user: User
    ):
        """POST /auth/login — 200 with valid credentials."""
        resp = await async_client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "benchpass123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert "expires_in" in body

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(
        self, async_client: AsyncClient, test_user: User
    ):
        """POST /auth/login — 401 with wrong password."""
        resp = await async_client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "incorrect" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_token_returns_200(
        self, async_client: AsyncClient, test_user: User
    ):
        """POST /auth/refresh — 200 with valid refresh token."""
        refresh = create_refresh_token(data={"sub": str(test_user.id)})
        resp = await async_client.post(
            "/auth/refresh",
            content=f'"{refresh}"',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# 2. User Endpoints (4 tests)
# ---------------------------------------------------------------------------

class TestUserEndpoints:
    """GET /users/me, PATCH /users/preferences, GET /users/working-hours."""

    @pytest.mark.asyncio
    async def test_get_me_returns_200(
        self, async_client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """GET /users/me — 200 with valid auth."""
        resp = await async_client.get("/users/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == test_user.email
        assert body["name"] == "Bench User"
        assert body["timezone"] == "America/Toronto"

    @pytest.mark.asyncio
    async def test_get_me_returns_401_without_auth(
        self, async_client: AsyncClient
    ):
        """GET /users/me — 403 without Authorization header (HTTPBearer default)."""
        resp = await async_client.get("/users/me")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_patch_preferences_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """PATCH /users/preferences — 200 updates preferences."""
        resp = await async_client.patch(
            "/users/preferences",
            headers=auth_headers,
            json={
                "preferred_earliest_time": "08:00",
                "preferred_latest_time": "19:00",
                "avoid_lunch": False,
                "min_break_minutes": 15,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["preferred_earliest_time"] == "08:00"
        assert body["preferred_latest_time"] == "19:00"
        assert body["avoid_lunch"] is False
        assert body["min_break_minutes"] == 15

    @pytest.mark.asyncio
    async def test_get_working_hours_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """GET /users/working-hours — 200 returns hours dict."""
        resp = await async_client.get(
            "/users/working-hours", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        expected_days = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]
        for day in expected_days:
            assert day in body
            assert "start" in body[day]
            assert "end" in body[day]
            assert "is_off_day" in body[day]


# ---------------------------------------------------------------------------
# 3. Appointment CRUD (5 tests)
# ---------------------------------------------------------------------------

class TestAppointmentCRUD:
    """POST/GET/PATCH/DELETE /appointments/."""

    @pytest.mark.asyncio
    async def test_create_appointment_returns_201(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """POST /appointments/ — 201 creates appointment."""
        tomorrow = date.today() + timedelta(days=1)
        resp = await async_client.post(
            "/appointments/",
            headers=auth_headers,
            json={
                "title": "Contract Test Meeting",
                "description": "Created by benchmark test",
                "start_time": datetime.combine(tomorrow, dt_time(10, 0)).isoformat(),
                "end_time": datetime.combine(tomorrow, dt_time(11, 0)).isoformat(),
                "duration_minutes": 60,
            },
        )
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert body["title"] == "Contract Test Meeting"
        assert body["status"] == "scheduled"
        assert "id" in body

    @pytest.mark.asyncio
    async def test_list_appointments_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """GET /appointments/ — 200 returns list."""
        resp = await async_client.get(
            "/appointments/", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "appointments" in body
        assert isinstance(body["appointments"], list)

    @pytest.mark.asyncio
    async def test_get_appointment_by_id_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """GET /appointments/{id} — 200 returns single appointment."""
        tomorrow = date.today() + timedelta(days=2)
        create_resp = await async_client.post(
            "/appointments/",
            headers=auth_headers,
            json={
                "title": "Fetch Me",
                "start_time": datetime.combine(tomorrow, dt_time(14, 0)).isoformat(),
                "end_time": datetime.combine(tomorrow, dt_time(15, 0)).isoformat(),
                "duration_minutes": 60,
            },
        )
        appt_id = create_resp.json()["id"]

        resp = await async_client.get(
            f"/appointments/{appt_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == appt_id
        assert resp.json()["title"] == "Fetch Me"

    @pytest.mark.asyncio
    async def test_patch_appointment_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """PATCH /appointments/{id} — 200 updates appointment."""
        tomorrow = date.today() + timedelta(days=3)
        create_resp = await async_client.post(
            "/appointments/",
            headers=auth_headers,
            json={
                "title": "Original Title",
                "start_time": datetime.combine(tomorrow, dt_time(9, 0)).isoformat(),
                "end_time": datetime.combine(tomorrow, dt_time(10, 0)).isoformat(),
                "duration_minutes": 60,
            },
        )
        appt_id = create_resp.json()["id"]

        new_start = datetime.combine(tomorrow, dt_time(11, 0)).isoformat()
        new_end = datetime.combine(tomorrow, dt_time(12, 0)).isoformat()
        resp = await async_client.patch(
            f"/appointments/{appt_id}",
            headers=auth_headers,
            json={
                "title": "Updated Title",
                "start_time": new_start,
                "end_time": new_end,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_appointment_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """DELETE /appointments/{id} — 200 cancels appointment."""
        tomorrow = date.today() + timedelta(days=4)
        create_resp = await async_client.post(
            "/appointments/",
            headers=auth_headers,
            json={
                "title": "To Cancel",
                "start_time": datetime.combine(tomorrow, dt_time(16, 0)).isoformat(),
                "end_time": datetime.combine(tomorrow, dt_time(17, 0)).isoformat(),
                "duration_minutes": 60,
            },
        )
        appt_id = create_resp.json()["id"]

        resp = await async_client.delete(
            f"/appointments/{appt_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert "cancelled" in resp.json()["message"].lower()

        verify = await async_client.get(
            f"/appointments/{appt_id}", headers=auth_headers
        )
        assert verify.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 4. Agent Endpoints (4 tests)
# ---------------------------------------------------------------------------

class TestAgentEndpoints:
    """POST /agent/search-availability, multi-person, create-appointment, chat."""

    @pytest.mark.asyncio
    async def test_search_availability_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """POST /agent/search-availability — 200 returns slots."""
        resp = await async_client.post(
            "/agent/search-availability",
            headers=auth_headers,
            json={
                "duration_minutes": 60,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "user_tz": "America/Toronto",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "slots" in body
        assert "duration_minutes" in body
        assert body["duration_minutes"] == 60

    @pytest.mark.asyncio
    async def test_multi_person_availability_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        second_user: User,
    ):
        """POST /agent/multi-person-availability — 200 returns common slots."""
        resp = await async_client.post(
            "/agent/multi-person-availability",
            headers=auth_headers,
            json={
                "attendee_ids": [test_user.id, second_user.id],
                "duration_minutes": 60,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "user_tz": "America/Toronto",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "slots" in body
        assert "duration_minutes" in body

    @pytest.mark.asyncio
    async def test_create_appointment_agent_returns_201(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """POST /agent/create-appointment — 201 on success."""
        tomorrow = date.today() + timedelta(days=1)
        resp = await async_client.post(
            "/agent/create-appointment",
            headers=auth_headers,
            json={
                "title": "Agent Created Meeting",
                "description": "Via agent endpoint",
                "start_time": datetime.combine(tomorrow, dt_time(10, 0)).isoformat(),
                "end_time": datetime.combine(tomorrow, dt_time(11, 0)).isoformat(),
                "duration_minutes": 60,
            },
        )
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert body["title"] == "Agent Created Meeting"
        assert "id" in body

    @pytest.mark.asyncio
    async def test_create_appointment_conflict_returns_409(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """POST /agent/create-appointment — 409 on scheduling conflict."""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Toronto")
        tomorrow = date.today() + timedelta(days=5)
        start = datetime.combine(tomorrow, dt_time(10, 0), tzinfo=tz).isoformat()
        end = datetime.combine(tomorrow, dt_time(11, 0), tzinfo=tz).isoformat()

        resp1 = await async_client.post(
            "/agent/create-appointment",
            headers=auth_headers,
            json={
                "title": "First Meeting",
                "start_time": start,
                "end_time": end,
                "duration_minutes": 60,
            },
        )
        assert resp1.status_code in (200, 201)

        resp2 = await async_client.post(
            "/agent/create-appointment",
            headers=auth_headers,
            json={
                "title": "Conflicting Meeting",
                "start_time": start,
                "end_time": end,
                "duration_minutes": 60,
            },
        )
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_chat_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """POST /agent/chat — 200 processes message."""
        resp = await async_client.post(
            "/agent/chat",
            headers=auth_headers,
            json={"message": "What can you help me with?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "response" in body
        assert "timestamp" in body


# ---------------------------------------------------------------------------
# 5. Calendar & Availability (3 tests)
# ---------------------------------------------------------------------------

class TestCalendarAvailability:
    """GET /calendar/, POST /availability/search/, GET /preferences/."""

    @pytest.mark.asyncio
    async def test_get_calendar_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """GET /calendar/ — 200 returns calendar appointments."""
        resp = await async_client.get(
            "/calendar/",
            headers=auth_headers,
            params={
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=14)).isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "appointments" in body
        assert isinstance(body["appointments"], list)

    @pytest.mark.asyncio
    async def test_availability_search_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """POST /availability/search/ — 200 returns available slots."""
        resp = await async_client.post(
            "/availability/search/",
            headers=auth_headers,
            json={
                "duration_minutes": 30,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "slots" in body
        assert isinstance(body["slots"], list)

    @pytest.mark.asyncio
    async def test_full_preferences_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """GET /preferences/ — 200 returns full profile response."""
        resp = await async_client.get(
            "/preferences/", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "profile" in body
        assert "preferences" in body
        assert "working_hours" in body
        assert body["profile"]["email"]
        assert body["preferences"]["preferred_earliest_time"]
        assert isinstance(body["working_hours"], dict)
