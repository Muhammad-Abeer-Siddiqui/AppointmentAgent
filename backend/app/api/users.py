"""User management API routes."""

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from typing import Optional, Dict
from datetime import datetime

from app.database import get_db_session
from app.database.models import User, WorkingHours
from app.auth import get_current_user
from app.schemas.profile import ProfileResponse, PreferencesResponse, WorkingHoursDetail


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=ProfileResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get current user profile."""
    return ProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        timezone=current_user.timezone or "UTC",
        locale=current_user.locale or "en",
    )


@router.patch("/me")
async def update_me(
    timezone: Optional[str] = Body(None, description="IANA timezone like 'America/Toronto'"),
    locale: Optional[str] = Body(None, description="Locale like 'en' or 'fr'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update user profile."""
    if timezone is not None:
        current_user.timezone = timezone
    if locale is not None:
        current_user.locale = locale

    db.commit()
    db.refresh(current_user)

    return ProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        timezone=current_user.timezone or "UTC",
        locale=current_user.locale or "en",
    )


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get user scheduling preferences."""
    pref = current_user.preferences
    if not pref:
        from app.database.models import UserPreferences
        pref = UserPreferences(user_id=current_user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)

    return PreferencesResponse(
        preferred_earliest_time=pref.preferred_earliest_time.strftime("%H:%M"),
        preferred_latest_time=pref.preferred_latest_time.strftime("%H:%M"),
        avoid_lunch=pref.avoid_lunch,
        min_break_minutes=pref.min_break_minutes,
        preferred_duration_minutes=pref.preferred_duration_minutes,
    )


@router.patch("/preferences")
async def update_preferences(
    preferred_earliest_time: Optional[str] = Body(
        None, description="HH:MM format, e.g. '10:00'"
    ),
    preferred_latest_time: Optional[str] = Body(
        None, description="HH:MM format, e.g. '18:00'"
    ),
    avoid_lunch: Optional[bool] = Body(None),
    min_break_minutes: Optional[int] = Body(None),
    preferred_duration_minutes: Optional[int] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update user scheduling preferences."""
    pref = current_user.preferences
    if not pref:
        from app.database.models import UserPreferences
        pref = UserPreferences(user_id=current_user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)

    if preferred_earliest_time is not None:
        pref.preferred_earliest_time = datetime.strptime(preferred_earliest_time, "%H:%M").time()
    if preferred_latest_time is not None:
        pref.preferred_latest_time = datetime.strptime(preferred_latest_time, "%H:%M").time()
    if avoid_lunch is not None:
        pref.avoid_lunch = avoid_lunch
    if min_break_minutes is not None:
        pref.min_break_minutes = min_break_minutes
    if preferred_duration_minutes is not None:
        pref.preferred_duration_minutes = preferred_duration_minutes

    db.commit()
    db.refresh(pref)

    return PreferencesResponse(
        preferred_earliest_time=pref.preferred_earliest_time.strftime("%H:%M"),
        preferred_latest_time=pref.preferred_latest_time.strftime("%H:%M"),
        avoid_lunch=pref.avoid_lunch,
        min_break_minutes=pref.min_break_minutes,
        preferred_duration_minutes=pref.preferred_duration_minutes,
    )


@router.get("/working-hours", response_model=Dict[str, WorkingHoursDetail])
async def get_working_hours(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get user working hours per day."""
    wh = current_user.working_hours
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    hours_data: Dict[str, WorkingHoursDetail] = {}
    for hour_record in wh:
        day_name = days[hour_record.day_of_week % 7] if hour_record.day_of_week >= 0 else "Monday"
        hours_data[day_name] = WorkingHoursDetail(
            start=hour_record.start_time.strftime("%H:%M"),
            end=hour_record.end_time.strftime("%H:%M"),
            is_off_day=hour_record.is_off_day,
        )

    # Fill in missing days with defaults
    for day in days:
        if day not in hours_data:
            hours_data[day] = WorkingHoursDetail(
                start="09:00",
                end="17:00",
                is_off_day=False,
            )

    return hours_data


@router.patch("/working-hours")
async def update_working_hours(
    day_of_week: int = Body(...),
    start_time: str = Body(...),
    end_time: str = Body(...),
    is_off_day: bool = Body(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update user working hours for a specific day."""
    from datetime import datetime as dt

    existing = db.query(WorkingHours).filter(
        WorkingHours.user_id == current_user.id,
        WorkingHours.day_of_week == day_of_week,
    ).first()

    if existing:
        existing.start_time = dt.strptime(start_time, "%H:%M").time()
        existing.end_time = dt.strptime(end_time, "%H:%M").time()
        existing.is_off_day = is_off_day
    else:
        new_wh = WorkingHours(
            user_id=current_user.id,
            day_of_week=day_of_week,
            start_time=dt.strptime(start_time, "%H:%M").time(),
            end_time=dt.strptime(end_time, "%H:%M").time(),
            is_off_day=is_off_day,
        )
        db.add(new_wh)

    db.commit()

    return {"message": f"Working hours for day {day_of_week} updated successfully"}
