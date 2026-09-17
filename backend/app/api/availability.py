"""Availability search API routes."""

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db_session
from app.database.models import User, Appointment
from app.schemas.availability import AvailabilitySearchResponse
from app.auth import get_current_user


router = APIRouter(prefix="/availability", tags=["Availability"])


@router.post("/search", response_model=AvailabilitySearchResponse)
async def search_availability(
    duration_minutes: int = Body(..., description="Required duration in minutes"),
    start_date: str = Body(..., description="Start date ISO, e.g. '2026-09-09'"),
    end_date: str = Body(..., description="End date ISO, e.g. '2026-09-15'"),
    preferred_earliest: Optional[str] = Body(None, description="HH:MM format"),
    preferred_latest: Optional[str] = Body(None, description="HH:MM format"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Search for available time slots using the deterministic scheduling engine."""
    from datetime import datetime as dt
    from app.scheduling.engine import generate_available_slots

    # Parse dates
    start_dt = dt.fromisoformat(start_date)
    end_dt = dt.fromisoformat(end_date)

    # Get user preferences as dict
    prefs = current_user.preferences
    preferences_dict = {}
    if prefs:
        preferences_dict = {
            "preferred_earliest_time": prefs.preferred_earliest_time.strftime("%H:%M") if prefs.preferred_earliest_time else "09:00",
            "preferred_latest_time": prefs.preferred_latest_time.strftime("%H:%M") if prefs.preferred_latest_time else "17:00",
            "avoid_lunch": prefs.avoid_lunch,
            "min_break_minutes": prefs.min_break_minutes,
            "preferred_duration_minutes": prefs.preferred_duration_minutes,
        }

    # Get working hours as list of dicts
    wh_list = current_user.working_hours
    working_hours_dicts = [
        {
            "day_of_week": wh.day_of_week,
            "start_time": wh.start_time,
            "end_time": wh.end_time,
            "is_off_day": wh.is_off_day,
        }
        for wh in wh_list
    ]

    # Get existing appointments as list of dicts
    existing_appts = db.query(Appointment).filter(
        Appointment.user_id == current_user.id,
        Appointment.status != "cancelled"
    ).all()

    existing_appointments_dicts = [
        {
            "start_time": appt.start_time,
            "end_time": appt.end_time,
        }
        for appt in existing_appts
    ]

    # Get user timezone
    user_tz = getattr(current_user, 'timezone', 'UTC') or "UTC"

    # Call the deterministic scheduling engine
    slots = generate_available_slots(
        date_range=(start_dt.date(), end_dt.date()),
        duration_minutes=duration_minutes,
        user_tz=user_tz,
        existing_appointments=existing_appointments_dicts,
        working_hours_list=working_hours_dicts if working_hours_dicts else None,
        preferences=preferences_dict if preferences_dict else None,
    )

    return {
        "slots": slots[:20],
        "duration_minutes": duration_minutes,
        "date_range": {"start": start_date, "end": end_date},
    }