"""Timezone utilities for the AI Appointment Scheduling Agent.

Provides conversion, localization, and formatting functions for handling
timezone-aware scheduling across different regions.
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple, List
from zoneinfo import ZoneInfo
import pytz


# Common timezone mappings
COMMON_TIMEZONES = {
    "North America": [
        "America/Toronto",
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Vancouver",
        "America/Halifax",
    ],
    "Europe": [
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Amsterdam",
        "Europe/Madrid",
        "Europe/Rome",
        "Europe/Zurich",
    ],
    "Asia": [
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Asia/Kolkata",
        "Asia/Dubai",
        "Asia/Singapore",
        "Asia/Hong_Kong",
    ],
    "Oceania": [
        "Australia/Sydney",
        "Australia/Melbourne",
        "Pacific/Auckland",
    ],
}


def get_utc_offset(tz_name: str, dt: Optional[datetime] = None) -> timedelta:
    """Get the UTC offset for a timezone at a specific datetime.

    Args:
        tz_name: IANA timezone name
        dt: Datetime to check offset at (defaults to now)

    Returns:
        UTC offset as timedelta
    """
    if dt is None:
        dt = datetime.now()

    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)

    return dt.astimezone(tz).utcoffset()


def format_utc_offset(tz_name: str, dt: Optional[datetime] = None) -> str:
    """Format UTC offset as string like '+05:00' or '-04:00'.

    Args:
        tz_name: IANA timezone name
        dt: Datetime to check (defaults to now)

    Returns:
        Formatted offset string
    """
    offset = get_utc_offset(tz_name, dt)
    total_seconds = int(offset.total_seconds())
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    sign = "+" if total_seconds >= 0 else "-"
    return f"{sign}{hours:02d}:{minutes:02d}"


def get_current_time_in_timezone(tz_name: str) -> datetime:
    """Get current time in a specific timezone.

    Args:
        tz_name: IANA timezone name

    Returns:
        Timezone-aware datetime
    """
    tz = ZoneInfo(tz_name)
    return datetime.now(tz)


def convert_to_timezone(
    dt: datetime,
    source_tz: str,
    target_tz: str,
) -> datetime:
    """Convert a datetime from one timezone to another.

    Args:
        dt: Datetime to convert
        source_tz: Source IANA timezone name
        target_tz: Target IANA timezone name

    Returns:
        Converted timezone-aware datetime
    """
    source = ZoneInfo(source_tz)
    target = ZoneInfo(target_tz)

    # Localize if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=source)

    return dt.astimezone(target)


def convert_utc_to_local(utc_dt: datetime, target_tz: str) -> datetime:
    """Convert UTC datetime to local timezone.

    Args:
        utc_dt: UTC datetime (naive or aware)
        target_tz: Target IANA timezone name

    Returns:
        Timezone-aware datetime in target timezone
    """
    target = ZoneInfo(target_tz)

    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=pytz.UTC)

    return utc_dt.astimezone(target)


def convert_local_to_utc(local_dt: datetime, source_tz: str) -> datetime:
    """Convert local datetime to UTC.

    Args:
        local_dt: Local datetime (naive or aware)
        source_tz: Source IANA timezone name

    Returns:
        UTC datetime
    """
    source = ZoneInfo(source_tz)

    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=source)

    return local_dt.astimezone(pytz.UTC)


def get_working_hours_boundaries(
    target_date: date,
    start_time: time,
    end_time: time,
    tz_name: str,
) -> Tuple[datetime, datetime]:
    """Get working hours boundaries as timezone-aware datetimes.

    Args:
        target_date: The date
        start_time: Work start time
        end_time: Work end time
        tz_name: IANA timezone name

    Returns:
        Tuple of (start_datetime, end_datetime) both timezone-aware
    """
    tz = ZoneInfo(tz_name)
    start_dt = datetime.combine(target_date, start_time).replace(tzinfo=tz)
    end_dt = datetime.combine(target_date, end_time).replace(tzinfo=tz)
    return start_dt, end_dt


def is_dst(tz_name: str, dt: Optional[datetime] = None) -> bool:
    """Check if a timezone is currently in daylight saving time.

    Args:
        tz_name: IANA timezone name
        dt: Datetime to check (defaults to now)

    Returns:
        True if in DST
    """
    if dt is None:
        dt = datetime.now()

    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)

    return dt.astimezone(tz).dst() != timedelta(0)


def get_timezone_abbreviation(tz_name: str, dt: Optional[datetime] = None) -> str:
    """Get timezone abbreviation (e.g., 'EST', 'PDT').

    Args:
        tz_name: IANA timezone name
        dt: Datetime to check (defaults to now)

    Returns:
        Timezone abbreviation string
    """
    if dt is None:
        dt = datetime.now()

    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)

    return dt.astimezone(tz).strftime("%Z")


def find_common_slot(
    attendee_timezones: List[str],
    preferred_start_hour: int = 9,
    preferred_end_hour: int = 17,
) -> Tuple[int, int]:
    """Find overlapping working hours across multiple timezones.

    Args:
        attendee_timezones: List of IANA timezone names
        preferred_start_hour: Preferred start hour (in UTC)
        preferred_end_hour: Preferred end hour (in UTC)

    Returns:
        Tuple of (start_hour_utc, end_hour_utc) representing common window
    """
    # Convert preferred hours to each timezone
    # Find the intersection
    now = datetime.now(pytz.UTC)

    # Simple approach: find hours where all timezones are within working hours
    common_start = preferred_start_hour
    common_end = preferred_end_hour

    for tz_name in attendee_timezones:
        tz = ZoneInfo(tz_name)
        local_now = now.astimezone(tz)

        # Get UTC offset
        offset_hours = local_now.utcoffset().total_seconds() / 3600

        # Convert preferred hours to UTC for this timezone
        tz_start = (preferred_start_hour - offset_hours) % 24
        tz_end = (preferred_end_hour - offset_hours) % 24

        # Adjust common window
        if tz_start > common_start:
            common_start = tz_start
        if tz_end < common_end:
            common_end = tz_end

    return (int(common_start), int(common_end))


def format_datetime_for_display(
    dt: datetime,
    tz_name: Optional[str] = None,
    format_str: str = "%Y-%m-%d %H:%M %Z",
) -> str:
    """Format datetime for user-friendly display.

    Args:
        dt: Datetime to format
        tz_name: Target timezone (converts if provided)
        format_str: strftime format string

    Returns:
        Formatted datetime string
    """
    if tz_name and dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)

    if tz_name:
        dt = dt.astimezone(ZoneInfo(tz_name))

    return dt.strftime(format_str)


def parse_datetime_with_timezone(
    datetime_str: str,
    tz_name: str,
) -> datetime:
    """Parse a datetime string and attach timezone.

    Args:
        datetime_str: ISO format datetime string
        tz_name: IANA timezone name

    Returns:
        Timezone-aware datetime
    """
    dt = datetime.fromisoformat(datetime_str)
    tz = ZoneInfo(tz_name)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)

    return dt
