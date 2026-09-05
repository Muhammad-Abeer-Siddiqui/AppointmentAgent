"""Availability search API routes."""

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, time as dt_time

from app.database import get_db_session
from app.database.models import User, UserPreferences, WorkingHours, Appointment, AvailabilityRule
from app.schemas.availability import AvailableSlot, AvailabilitySearchResponse
from app.auth import get_current_user


router = APIRouter(prefix="/availability", tags=["Availability"])


def _get_user_timezone(current_user) -> str:
    """Get user's timezone."""
    return getattr(current_user, 'timezone', 'UTC')


def _parse_time_str(time_str: str) -> dt_time:
    """Parse HH:MM time string."""
    parts = time_str.split(":")
    return dt_time(int(parts[0]), int(parts[1]))


def _format_time(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def _is_within_working_hours(dt: datetime, working_hours_list: List[WorkingHours], tz: str) -> bool:
    """Check if a datetime falls within user's working hours."""
    from app.scheduling.engine import is_within_working_hours as _check_wh
    return _check_wh(dt, working_hours_list, tz)


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
    """Search for available time slots."""
    from datetime import datetime as dt

    # Parse dates
    start_dt = dt.fromisoformat(start_date)
    end_dt = dt.fromisoformat(end_date)

    # Get user preferences
    prefs = current_user.preferences
    if not prefs:
        from app.database.models import UserPreferences
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    # Get working hours
    wh_list = current_user.working_hours

    # Get existing appointments
    existing_appts = db.query(Appointment).filter(
        Appointment.user_id == current_user.id,
        Appointment.status != "cancelled"
    ).all()

    # Convert date range to slots
    slots = []
    current = start_dt.date()

    while current <= end_dt.date():
        day_start = dt.combine(current, dt_time(9, 0))  # Default
        day_end = dt.combine(current, dt_time(17, 0))  # Default

        # Check working hours for this day
        day_wh = [wh for wh in wh_list if wh.day_of_week == current.weekday()]
        if day_wh:
            day_start = dt.combine(current, day_wh[0].start_time)
            day_end = dt.combine(current, day_wh[0].end_time)

        # Skip if outside working hours entirely
        if day_end <= day_start:
            current = (current + timedelta(days=1))
            continue

        # Generate potential slots within this day
        slot_start = day_start
        while slot_start + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = slot_start + timedelta(minutes=duration_minutes)

            # Check for conflicts with existing appointments
            has_conflict = False
            for appt in existing_appts:
                # Strip tzinfo for comparison with naive slot times
                appt_start = appt.start_time.replace(tzinfo=None) if appt.start_time.tzinfo else appt.start_time
                appt_end = appt.end_time.replace(tzinfo=None) if appt.end_time.tzinfo else appt.end_time
                if (appt_start <= slot_end and appt_end >= slot_start):
                    slot_start = appt_end
                    has_conflict = True
                    break

            if not has_conflict:
                # Apply preferences
                score = _calculate_slot_score(slot_start, slot_end, prefs, wh_list)

                slots.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "score": score,
                    "date": current.isoformat(),
                })

            slot_start += timedelta(minutes=duration_minutes)

        current = (current + timedelta(days=1))

    # Sort by score (highest first)
    slots.sort(key=lambda x: x["score"], reverse=True)

    return {
        "slots": slots[:20],
        "duration_minutes": duration_minutes,
        "date_range": {"start": start_date, "end": end_date},
    }


def _calculate_slot_score(
    slot_start: datetime,
    slot_end: datetime,
    prefs: Any,
    wh_list: List[Any],
) -> int:
    """Calculate a score for a time slot (higher = better)."""
    score = 50  # Base score

    # Prefer mornings/afternoons based on preferences
    mid_time = slot_start.time()
    earliest = prefs.preferred_earliest_time
    latest = prefs.preferred_latest_time

    if earliest <= mid_time <= latest:
        score += 20  # Within preferred window

    # Penalize lunch hours if preferred
    if hasattr(prefs, 'avoid_lunch') and prefs.avoid_lunch:
        lunch_start = dt_time(12, 0)
        lunch_end = dt_time(13, 0)
        mid = mid_time
        if lunch_start <= mid <= lunch_end:
            score -= 15

    # Reward earliest availability
    score += min(20, (slot_start.hour * 60 + slot_start.minute) // 30)

    return score