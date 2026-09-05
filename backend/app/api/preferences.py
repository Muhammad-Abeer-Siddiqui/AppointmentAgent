"""User preferences API routes for the AI Appointment Scheduling Agent."""

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db_session
from app.database.models import User, UserPreferences, WorkingHours
from app.auth import get_current_user
from app.schemas import ProfileResponse, PreferencesResponse, FullProfileResponse
from app.schemas.profile import WorkingHoursDetail


router = APIRouter(prefix="/preferences", tags=["Preferences"])


@router.get("/", response_model=None)
async def get_all_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FullProfileResponse:
    """Get all user preferences including profile, working hours, and scheduling prefs."""
    from app.api.users import get_me
    profile = await get_me(current_user=current_user, db=db)

    prefs = current_user.preferences
    wh_data = current_user.working_hours

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    working_hours_data = {}
    for hour_record in wh_data:
        day_name = days[hour_record.day_of_week % 7] if hour_record.day_of_week >= 0 else "Monday"
        working_hours_data[day_name] = WorkingHoursDetail(
            start=hour_record.start_time.strftime("%H:%M"),
            end=hour_record.end_time.strftime("%H:%M"),
            is_off_day=hour_record.is_off_day,
        )

    # Fill in missing days
    for i, day in enumerate(days):
        if day not in working_hours_data:
            working_hours_data[day] = WorkingHoursDetail(
                start="09:00",
                end="17:00",
                is_off_day=False,
            )

    preferences_data = PreferencesResponse(
        preferred_earliest_time=prefs.preferred_earliest_time.strftime("%H:%M") if prefs else "09:00",
        preferred_latest_time=prefs.preferred_latest_time.strftime("%H:%M") if prefs else "17:00",
        avoid_lunch=prefs.avoid_lunch if prefs else False,
        min_break_minutes=prefs.min_break_minutes if prefs else 30,
        preferred_duration_minutes=prefs.preferred_duration_minutes if prefs else 60,
    )

    profile_data = ProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        timezone=current_user.timezone or "UTC",
        locale=current_user.locale or "en",
    )

    return FullProfileResponse(
        profile=profile_data,
        preferences=preferences_data,
        working_hours=working_hours_data,
    )


@router.patch("/profile", response_model=None)
async def update_profile(
    name: Optional[str] = Body(None, description="User's full name"),
    timezone: Optional[str] = Body(
        None, description="IANA timezone like 'America/Toronto'"
    ),
    locale: Optional[str] = Body(None, description="Locale like 'en' or 'fr'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update user profile information."""
    if name is not None:
        current_user.name = name
    if timezone is not None:
        current_user.timezone = timezone
    if locale is not None:
        current_user.locale = locale

    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "timezone": current_user.timezone,
        "locale": current_user.locale,
    }