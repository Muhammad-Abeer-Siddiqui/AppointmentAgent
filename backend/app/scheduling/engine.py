"""Deterministic scheduling engine - CODE handles SCHEDULING and TRUTH.

This module implements the core scheduling logic that the AI agent calls.
The LLM must NEVER determine availability directly - it must use these tools.
"""

from datetime import datetime, date, time, timedelta, time as dt_time
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

import pytz
from zoneinfo import ZoneInfo

from app.scheduling.timezone_utils import (
    convert_to_timezone,
    convert_utc_to_local,
    convert_local_to_utc,
    get_current_time_in_timezone,
    format_datetime_for_display,
)


# =============================================================================
# TIMEZONE HELPERS
# =============================================================================

def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC."""
    if dt.tzinfo is None:
        # Assume naive datetime is local/user timezone
        return dt.astimezone(pytz.UTC)
    return dt.astimezone(pytz.UTC)


def from_utc(dt: datetime, target_tz: str) -> datetime:
    """Convert a UTC datetime to target timezone."""
    tz = ZoneInfo(target_tz)
    return dt.astimezone(tz)


def localize_naive(dt: datetime, tz_name: str) -> datetime:
    """Localize a naive datetime to a given timezone."""
    tz = ZoneInfo(tz_name)
    return dt.replace(tzinfo=tz)


def resolve_constraint_date(
    date_str: str,
    reference_date: date,
    user_tz: str,
) -> date:
    """Resolve a natural language date constraint to an actual date."""
    from datetime import datetime as dt

    d = dt.fromisoformat(date_str)

    # If just a year/month/day without timezone context
    if d.year > 2030:  # Likely a full date already
        return d.date()

    # Apply user timezone logic
    # If month is "next month" etc, we'd handle that here
    # For now, just return the date as parsed
    return d.date()


# =============================================================================
# WORKING HOURS
# =============================================================================

def get_working_hours_for_day(
    user_tz: str,
    target_date: date,
    working_hours_list: Optional[List[dict]] = None,
) -> Optional[Tuple[time, time]]:
    """Get working hours for a specific date.

    Args:
        user_tz: User's IANA timezone
        target_date: The date to check
        working_hours_list: List of working hour rules (optional - if None, 24/7)

    Returns:
        Tuple of (start_time, end_time) or None if no working hours (24/7)
    """
    if not working_hours_list:
        # No working hours configured - 24/7 availability
        return (time(0, 0), time(23, 59, 59))

    tz = ZoneInfo(user_tz)

    # Find matching working hours rule for this day of week
    # Python: Monday=0, Sunday=6
    # The database stores day_of_week in Python convention (0=Monday, 6=Sunday)
    day_of_week = target_date.weekday()  # 0=Monday, 6=Sunday

    for wh in working_hours_list:
        # The database stores day_of_week in Python convention (0=Monday, 6=Sunday)
        wh_day = wh.get("day_of_week", 0)
        # Convert: if wh_day is ISO (1=Monday) to Python (0=Monday)
        if wh_day >= 1:
            wh_day = wh_day - 1  # ISO 1-7 -> Python 0-6

        if wh_day == day_of_week and not wh.get("is_off_day", False):
            start_time = wh["start_time"]
            end_time = wh["end_time"]
            return (start_time, end_time)

    return None


# =============================================================================
# CONFLICT DETECTION
# =============================================================================

def parse_appointment_time(
    start_str: str,
    end_str: str,
    tz_name: str,
) -> Tuple[datetime, datetime]:
    """Parse appointment time strings into timezone-aware datetimes.

    Args:
        start_str: ISO format datetime string
        end_str: ISO format datetime string
        tz_name: IANA timezone name

    Returns:
        Tuple of (start_dt, end_dt) both timezone-aware
    """
    from_zone = ZoneInfo("UTC")
    to_zone = ZoneInfo(tz_name)

    # Parse as UTC if no timezone info
    start_naive = datetime.fromisoformat(start_str)
    end_naive = datetime.fromisoformat(end_str)

    # If naive, assume UTC
    if start_naive.tzinfo is None:
        start_naive = start_naive.replace(tzinfo=from_zone)
    if end_naive.tzinfo is None:
        end_naive = end_naive.replace(tzinfo=from_zone)

    # Convert to target timezone
    start_dt = start_naive.astimezone(to_zone)
    end_dt = end_naive.astimezone(to_zone)

    return start_dt, end_dt


def detect_conflict(
    new_start: datetime,
    new_end: datetime,
    existing_appointments: List[dict],
    user_tz: str,
) -> bool:
    """Detect if a new appointment conflicts with existing ones.

    Args:
        new_start: Proposed appointment start (timezone-aware)
        new_end: Proposed appointment end (timezone-aware)
        existing_appointments: List of existing appointments
        user_tz: User's timezone for display

    Returns:
        True if conflict detected, False otherwise
    """
    new_start_utc = new_start.astimezone(pytz.UTC)
    new_end_utc = new_end.astimezone(pytz.UTC)

    for appt in existing_appointments:
        appt_start_utc = appt["start_time"].astimezone(pytz.UTC) if appt["start_time"].tzinfo else appt["start_time"]
        appt_end_utc = appt["end_time"].astimezone(pytz.UTC) if appt["end_time"].tzinfo else appt["end_time"]

        # Check overlap: new starts before existing ends AND new ends after existing starts
        if new_start_utc < appt_end_utc and new_end_utc > appt_start_utc:
            return True

    return False


# =============================================================================
# RECURRENCE EXPANSION
# =============================================================================

def expand_recurrence(
    recurrence_rule: str,
    start_date: date,
    duration_minutes: int,
    range_end: date,
    interval: int = 1,
) -> List[date]:
    """Expand a simple recurrence rule into a list of dates.

    Supported rules:
    - "daily": Every N days
    - "weekly": Every N weeks on the same day of week
    - "monthly": Every N months on the same day of month

    Args:
        recurrence_rule: One of "daily", "weekly", "monthly"
        start_date: The date of the first occurrence
        duration_minutes: Duration (used to check if appointment fits in day)
        range_end: Don't generate dates beyond this
        interval: Interval between occurrences (default 1)

    Returns:
        List of dates where occurrences should be placed
    """
    dates = []
    current = start_date

    if recurrence_rule == "daily":
        while current <= range_end:
            dates.append(current)
            current = current + timedelta(days=interval)

    elif recurrence_rule == "weekly":
        while current <= range_end:
            dates.append(current)
            current = current + timedelta(weeks=interval)

    elif recurrence_rule == "monthly":
        while current <= range_end:
            dates.append(current)
            # Move to next month
            month = current.month + interval
            year = current.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            # Handle day overflow (e.g., Jan 31 + 1 month -> Feb 28)
            max_day = 28  # Safe minimum
            try:
                from calendar import monthrange
                _, max_day = monthrange(year, month)
            except (ValueError, OverflowError):
                pass
            day = min(current.day, max_day)
            current = date(year, month, day)

    return dates


# =============================================================================
# SLOT GENERATION
# =============================================================================

def generate_available_slots(
    date_range: Tuple[date, date],
    duration_minutes: int,
    user_tz: str,
    existing_appointments: List[dict],
    working_hours_list: Optional[List[dict]] = None,
    preferences: Optional[dict] = None,
    buffers_minutes: int = 15,
) -> List[Dict[str, Any]]:
    """Generate a ranked list of available time slots.

    This is the core deterministic scheduling engine. It NEVER relies on the LLM
    to determine availability - it calculates it from working hours, existing
    appointments, and preferences.

    Args:
        date_range: Tuple of (start_date, end_date)
        duration_minutes: Desired appointment duration
        user_tz: User's IANA timezone
        working_hours_list: User's working hours per day (optional - if None, 24/7)
        existing_appointments: Existing appointments to avoid
        preferences: User preferences dict
        buffers_minutes: Buffer between appointments

    Returns:
        List of available slots sorted by score (descending)
    """
    from app.database.models import UserPreferences as UP

    if preferences is None:
        preferences = {}

    start_date, end_date = date_range
    tz = ZoneInfo(user_tz)

    slots = []

    # Iterate through each day in the range
    current_date = start_date
    while current_date <= end_date:
        # Get working hours for this day
        wh = get_working_hours_for_day(user_tz, current_date, working_hours_list) if working_hours_list else None

        if wh is None:
            # No working hours configured - use 24/7 (full day)
            day_start = datetime.combine(current_date, time(0, 0)).replace(tzinfo=tz)
            day_end = datetime.combine(current_date, time(23, 59, 59)).replace(tzinfo=tz)
        else:
            wh_start, wh_end = wh
            # Convert to datetime objects for this specific date
            day_start = datetime.combine(current_date, wh_start).replace(tzinfo=tz)
            day_end = datetime.combine(current_date, wh_end).replace(tzinfo=tz)

        # Filter out existing appointments from the available window
        # Create a list of "busy" intervals
        busy_intervals = []
        for appt in existing_appointments:
            # Only consider appointments on this date (or overlapping)
            appt_start = appt["start_time"]
            appt_end = appt["end_time"]

            # If appointment has timezone info, convert; otherwise assume UTC
            if appt_start.tzinfo is None:
                appt_start = appt_start.replace(tzinfo=tz)
            if appt_end.tzinfo is None:
                appt_end = appt_end.replace(tzinfo=tz)

            # Check if this appointment overlaps with our day
            if appt_start.date() == current_date:
                # Clip to day boundaries
                busy_start = max(day_start, appt_start)
                busy_end = min(day_end, appt_end)
                if busy_start < busy_end:
                    busy_intervals.append((busy_start, busy_end))

        # Sort busy intervals by start time
        busy_intervals.sort()

        # Generate available slots within working hours, avoiding busy intervals
        current_slot_start = day_start

        for busy_start, busy_end in busy_intervals:
            # Available space before this busy interval
            if current_slot_start + timedelta(minutes=buffers_minutes) < busy_start:
                available_end = busy_start - timedelta(minutes=1)
                available_duration = (available_end - current_slot_start).seconds // 60

                if available_duration >= duration_minutes:
                    slot_end = current_slot_start + timedelta(minutes=duration_minutes)
                    if slot_end <= available_end:
                        score_result = _calculate_slot_score(
                            current_slot_start, slot_end, preferences
                        )
                        slots.append({
                            "start": current_slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "score": score_result["score"],
                            "reasons": score_result["reasons"],
                            "date": current_date.isoformat(),
                            "timezone": user_tz,
                        })

            # Move current slot start past the busy interval + buffer
            current_slot_start = busy_end + timedelta(minutes=buffers_minutes)

        # Available space after the last busy interval
        if current_slot_start + timedelta(minutes=buffers_minutes) < day_end:
            available_end = day_end - timedelta(minutes=1)
            available_duration = (available_end - current_slot_start).seconds // 60

            if available_duration >= duration_minutes:
                slot_end = current_slot_start + timedelta(minutes=duration_minutes)
                if slot_end <= available_end:
                    score_result = _calculate_slot_score(
                        current_slot_start, slot_end, preferences
                    )
                    slots.append({
                        "start": current_slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "score": score_result["score"],
                        "reasons": score_result["reasons"],
                        "date": current_date.isoformat(),
                        "timezone": user_tz,
                    })

        current_date = (current_date + timedelta(days=1))

    # Sort slots by score (highest first = best match)
    slots.sort(key=lambda x: x["score"], reverse=True)

    return slots


def _calculate_slot_score(
    slot_start: datetime,
    slot_end: datetime,
    preferences: dict,
) -> Dict[str, Any]:
    """Calculate a deterministic score for a time slot with explanation.

    Higher score = better match for user preferences.

    Score components:
    - Preference match (0-25 points)
    - Earliest availability bonus (0-10 points)
    - Lunch avoidance penalty (0-20 points subtracted, only if avoid_lunch=True)
    - Working hours proximity (0-5 points)

    Returns:
        Dict with "score" (int) and "reasons" (list of str)
    """
    score = 50  # Base score
    reasons = ["Standard time slot"]

    # Get preferred time window
    pref = preferences or {}
    earliest = pref.get("preferred_earliest", "09:00")
    latest = pref.get("preferred_latest", "17:00")
    avoid_lunch = pref.get("avoid_lunch", True)
    min_break = pref.get("min_break_minutes", 15)

    # Parse preference times
    try:
        earliest_h, earliest_m = map(int, earliest.split(":"))
        latest_h, latest_m = map(int, latest.split(":"))
        preferred_earliest = datetime.combine(slot_end.date(), dt_time(earliest_h, earliest_m))
        preferred_latest = datetime.combine(slot_end.date(), dt_time(latest_h, latest_m))
    except (ValueError, AttributeError):
        preferred_earliest = datetime.combine(slot_end.date(), dt_time(9, 0))
        preferred_latest = datetime.combine(slot_end.date(), dt_time(17, 0))

    slot_mid = slot_start + (slot_end - slot_start) / 2
    # Strip tzinfo for comparison with naive preferred times
    slot_mid_naive = slot_mid.replace(tzinfo=None)

    # Preference match: does the slot fall within preferred window?
    if preferred_earliest <= slot_mid_naive <= preferred_latest:
        score += 25
        reasons.append("Within your preferred time window")

    # Earliest availability bonus: earlier slots get slight boost
    slot_minutes_from_midnight = slot_start.hour * 60 + slot_start.minute
    if slot_minutes_from_midnight < 720:  # Before noon
        score += 10
        reasons.append("Morning slot")

    # Lunch avoidance (only if preference says to avoid lunch)
    if avoid_lunch:
        slot_end_naive = slot_end.replace(tzinfo=None)
        lunch_start = datetime.combine(slot_end.date(), dt_time(12, 0))
        lunch_end = datetime.combine(slot_end.date(), dt_time(13, 0))
        if lunch_start <= slot_end_naive <= lunch_end:
            score -= 20
            reasons.append("Overlaps with lunch hour")
        else:
            reasons.append("Avoids lunch hour")

    # Working hours proximity
    if 9 <= slot_start.hour < 17:
        score += 5
        reasons.append("During standard working hours")

    # Round to nearest 15 minutes for tidiness
    score = round(score / 15) * 15
    score = max(0, min(100, score))  # Clamp to 0-100

    return {"score": score, "reasons": reasons}


# =============================================================================
# MULTI-PERSON AVAILABILITY
# =============================================================================

def find_multi_person_availability(
    attendee_ids: List[int],
    date_range: Tuple[date, date],
    duration_minutes: int,
    user_tz: str,
    db_session,
) -> List[Dict[str, Any]]:
    """Find time slots when ALL attendees are available.

    This is the key multi-person scheduling function. It calculates the
    intersection of availability across multiple calendars.

    Args:
        attendee_ids: List of user IDs to find common availability for
        date_range: Tuple of (start_date, end_date)
        duration_minutes: Desired appointment duration
        user_tz: Primary user's timezone for display
        db_session: Database session for querying calendars

    Returns:
        List of available slots ranked by score
    """
    from app.database.models import User, Appointment, WorkingHours, UserPreferences

    # Get all attendees' data
    attendees = []
    for attendee_id in attendee_ids:
        attendee = db_session.query(User).get(attendee_id)
        if attendee:
            prefs = attendee.preferences or UP(user_id=attendee.id)
            wh = attendee.working_hours or []

            # Get existing appointments
            from sqlalchemy import select

            # Query appointments for this attendee
            stmt = select(Appointment).filter(
                Appointment.user_id == attendee_id,
                Appointment.status != "cancelled"
            )
            appts_result = db_session.execute(stmt).scalars().all()
            appts = appts_result if appts_result else []

            attendees.append({
                "id": attendee.id,
                "name": attendee.name,
                "email": attendee.email,
                "timezone": attendee.timezone or user_tz,
                "preferences": prefs,
"working_hours": [{"day_of_week": w.day_of_week, "start_time": w.start_time, "end_time": w.end_time, "is_off_day": w.is_off_day} for w in wh],
                "appointments": appts,
            })

    if len(attendees) < 2:
        # Single person - just return their availability
        # For now, return empty - should not happen in multi-person use
        return []

    # Get the first attendee's working hours as reference
    # Then intersect with others
    reference_attendee = attendees[0]
    reference_wh = reference_attendee["working_hours"]

    # Generate availability for first attendee
    from datetime import date as d_date
    from app.scheduling.engine import generate_available_slots

    first_slots = generate_available_slots(
        date_range=date_range,
        duration_minutes=duration_minutes,
        user_tz=reference_attendee["timezone"],
        working_hours_list=reference_wh,
        existing_appointments=[
            {
                "start_time": appt.start_time,
                "end_time": appt.end_time,
            }
            for appt in reference_attendee["appointments"]
        ],
        preferences=reference_attendee["preferences"].__dict__ if hasattr(
            reference_attendee["preferences"], '__dict__'
        ) else reference_attendee["preferences"],
    )

    # Intersect with other attendees' availability
    # For each slot from first attendee, check if all others are also free
    valid_slots = []

    for slot in first_slots:
        slot_start = datetime.fromisoformat(slot["start"])
        slot_end = datetime.fromisoformat(slot["end"])

        all_free = True

        # Check each other attendee
        for other in attendees[1:]:
            other_free = False

            # Check if this slot falls within their working hours
            wh_result = get_working_hours_for_day(
                other["timezone"],
                slot_start.date(),
                other["working_hours"],
            )

            if wh_result is None:
                # No working hours defined for this day - assume available
                other_free = True
            else:
                wh_start, wh_end = wh_result
                slot_dt_start = datetime.combine(slot_start.date(), wh_start)
                slot_dt_end = datetime.combine(slot_start.date(), wh_end)

                # Check if slot is within working hours
                if slot_dt_start >= datetime.combine(slot_start.date(), wh_start) and \
                   slot_dt_end <= datetime.combine(slot_start.date(), wh_end):
                    # Now check against their existing appointments
                    for appt in other["appointments"]:
                        appt_start = appt["start_time"]
                        appt_end = appt["end_time"]

                        # Convert to same timezone for comparison
                        if appt_start.tzinfo is None:
                            appt_start = appt_start.replace(tzinfo=ZoneInfo(other["timezone"]))
                        if appt_end.tzinfo is None:
                            appt_end = appt_end.replace(tzinfo=ZoneInfo(other["timezone"]))

                        # Check overlap
                        if not (slot_end <= appt_start or slot_start >= appt_end):
                            # Conflict found
                            other_free = False
                            break
                    else:
                        other_free = True

            if not other_free:
                all_free = False
                break

        if all_free:
            valid_slots.append({
                "start": slot["start"],
                "end": slot["end"],
                "score": slot["score"],
                "date": slot["date"],
                "timezone": user_tz,
            })

    # Sort by score
    valid_slots.sort(key=lambda x: x["score"], reverse=True)

    return valid_slots[:15]  # Return top 15 slots
