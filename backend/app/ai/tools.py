"""Agent tools that execute scheduling operations.

These tools are called by the AI agent through function calling.
They handle database operations, validation, and return structured results
that the AI agent can present to the user.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.database.models import User, Appointment, UserPreferences
from app.scheduling.engine import (
    generate_available_slots,
    detect_conflict,
)
from app.scheduling.timezone_utils import (
    get_current_time_in_timezone,
    format_datetime_for_display,
)
from app.services.google_calendar import GoogleCalendarService
from app.services.sync_service import (
    is_google_connected,
    sync_user_to_google,
    sync_user_from_google,
    async_update_event,
    async_delete_event,
)


async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int,
    db: Session,
) -> Any:
    """Execute a tool call with database access.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments from the AI
        user_id: Authenticated user ID
        db: Database session

    Returns:
        Tool result dict
    """
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    # Execute the appropriate tool
    if tool_name == "search_availability":
        return await _search_availability(arguments, user, db)
    elif tool_name == "create_appointment":
        return await _create_appointment(arguments, user, db)
    elif tool_name == "multi_person_availability":
        return await _multi_person_availability(arguments, user, db)
    elif tool_name == "update_appointment":
        return await _update_appointment(arguments, user, db)
    elif tool_name == "cancel_appointment":
        return await _cancel_appointment(arguments, user, db)
    elif tool_name == "get_user_profile":
        return await _get_user_profile(user, db)
    elif tool_name == "set_user_preferences":
        return await _set_user_preferences(arguments, user, db)
    elif tool_name == "get_calendar":
        return await _get_calendar(arguments, user, db)
    elif tool_name == "confirm_action":
        # Confirmation is handled at a higher level
        return arguments
    elif tool_name == "sync_to_google_calendar":
        return await _sync_to_google(user, db)
    elif tool_name == "sync_from_google_calendar":
        return await _sync_from_google(user, db)
    elif tool_name == "create_recurring_appointment":
        return await _create_recurring_appointment(arguments, user, db)
    elif tool_name == "cancel_recurring_series":
        return await _cancel_recurring_series(arguments, user, db)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def _search_availability(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Search for available time slots."""
    from app.database.models import WorkingHours

    duration = arguments.get("duration_minutes", 60)
    start_date_str = arguments.get("start_date")
    end_date_str = arguments.get("end_date")
    user_tz = arguments.get("user_tz", user.timezone or "UTC")

    # Parse dates
    start_date = datetime.fromisoformat(start_date_str).date() if start_date_str else datetime.utcnow().date()
    end_date = datetime.fromisoformat(end_date_str).date() if end_date_str else (start_date + timedelta(days=7))

# Get user's working hours as dicts
    wh_list = [
        {
            "day_of_week": wh.day_of_week,
            "start_time": wh.start_time,
            "end_time": wh.end_time,
            "is_off_day": wh.is_off_day,
        }
        for wh in user.working_hours
    ]

    # Get existing appointments
    existing_appts = db.query(Appointment).filter(
        Appointment.user_id == user.id,
        Appointment.status != "cancelled",
    ).all()

    appt_dicts = [
        {
            "start_time": appt.start_time,
            "end_time": appt.end_time,
        }
        for appt in existing_appts
    ]

    # Get preferences
    prefs = user.preferences
    preferences = {
        "preferred_earliest": prefs.preferred_earliest_time.strftime("%H:%M") if prefs and prefs.preferred_earliest_time else "09:00",
        "preferred_latest": prefs.preferred_latest_time.strftime("%H:%M") if prefs and prefs.preferred_latest_time else "17:00",
        "avoid_lunch": prefs.avoid_lunch if prefs else True,
        "min_break_minutes": prefs.min_break_minutes if prefs else 30,
    }

    # Generate available slots
    slots = generate_available_slots(
        date_range=(start_date, end_date),
        duration_minutes=duration,
        user_tz=user_tz,
        working_hours_list=wh_list,
        existing_appointments=appt_dicts,
        preferences=preferences,
    )

    return {
        "slots": [
            {
                "id": i,
                "start": slot.get("start"),
                "end": slot.get("end"),
                "score": slot.get("score", 50),
                "date": slot.get("date"),
            }
            for i, slot in enumerate(slots[:10])
        ],
        "duration_minutes": duration,
        "date_range": {"start": start_date_str, "end": end_date_str},
        "total_found": len(slots),
    }


async def _create_appointment(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Create an appointment with conflict detection."""
    title = arguments.get("title", "Untitled")
    description = arguments.get("description", "")
    start_time_str = arguments.get("start_time")
    end_time_str = arguments.get("end_time")
    duration = arguments.get("duration_minutes", 60)

    # Parse datetimes
    start_dt = datetime.fromisoformat(start_time_str)
    end_dt = datetime.fromisoformat(end_time_str)

    # Check for conflicts with existing appointments
    existing_appts = db.query(Appointment).filter(
        Appointment.user_id == user.id,
        Appointment.status != "cancelled",
    ).all()

    # Convert to timezone-naive for comparison
    start_naive = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
    end_naive = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt

    conflicts = []
    for appt in existing_appts:
        appt_start = appt.start_time.replace(tzinfo=None) if appt.start_time.tzinfo else appt.start_time
        appt_end = appt.end_time.replace(tzinfo=None) if appt.end_time.tzinfo else appt.end_time

        if start_naive < appt_end and end_naive > appt_start:
            conflicts.append({
                "id": appt.id,
                "title": appt.title,
                "start": appt.start_time.isoformat(),
                "end": appt.end_time.isoformat(),
            })

    if conflicts:
        return {
            "success": False,
            "error": "Conflict with existing appointments",
            "conflicts": conflicts,
        }

    # Create the appointment
    appointment = Appointment(
        user_id=user.id,
        title=title,
        description=description,
        start_time=start_dt,
        end_time=end_dt,
        duration_minutes=duration,
        status="scheduled",
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # Two-way sync: Sync to Google Calendar if user has it connected
    sync_result = await sync_user_to_google(user.id, db)

    result = {
        "success": True,
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat(),
        "end": appointment.end_time.isoformat(),
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }

    if sync_result["success"]:
        result["google_sync"] = {
            "synced": True,
            "google_event_id": sync_result.get("event_id"),
        }
    else:
        result["google_sync"] = {
            "synced": False,
            "error": sync_result.get("error", "Sync failed"),
        }

    return result


async def _multi_person_availability(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Find common availability for multiple attendees."""
    from app.scheduling.engine import find_multi_person_availability

    attendee_ids = arguments.get("attendee_ids", [])
    duration = arguments.get("duration_minutes", 60)
    start_date_str = arguments.get("start_date")
    end_date_str = arguments.get("end_date")
    user_tz = arguments.get("user_tz", user.timezone or "UTC")

    # Parse dates
    start_date = datetime.fromisoformat(start_date_str).date() if start_date_str else datetime.utcnow().date()
    end_date = datetime.fromisoformat(end_date_str).date() if end_date_str else (start_date + timedelta(days=7))

    # Include the current user if not in the list
    if user.id not in attendee_ids:
        attendee_ids.append(user.id)

    # Find multi-person availability
    slots = find_multi_person_availability(
        attendee_ids=attendee_ids,
        date_range=(start_date, end_date),
        duration_minutes=duration,
        user_tz=user_tz,
        db_session=db,
    )

    return {
        "slots": [
            {
                "id": i,
                "start": slot.get("start"),
                "end": slot.get("end"),
                "score": slot.get("score", 50),
                "date": slot.get("date"),
            }
            for i, slot in enumerate(slots[:10])
        ],
        "duration_minutes": duration,
        "attendee_ids": attendee_ids,
        "total_found": len(slots),
    }


async def _update_appointment(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Update an existing appointment."""
    appointment_id = arguments.get("appointment_id")
    if not appointment_id:
        return {"error": "Missing appointment_id"}

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.user_id == user.id,
    ).first()

    if not appointment:
        return {"error": "Appointment not found"}

    # Update fields if provided
    if "title" in arguments:
        appointment.title = arguments["title"]
    if "description" in arguments:
        appointment.description = arguments["description"]
    if "start_time" in arguments:
        appointment.start_time = datetime.fromisoformat(arguments["start_time"])
    if "end_time" in arguments:
        appointment.end_time = datetime.fromisoformat(arguments["end_time"])

    db.commit()
    db.refresh(appointment)

    # Two-way sync: Update Google Calendar if user has it connected and event was synced
    google_sync_result = {"synced": False}
    if appointment.google_calendar_event_id:
        google_service = GoogleCalendarService(user, db)
        if google_service.is_connected():
            event_data = {
                "title": appointment.title,
                "description": appointment.description,
                "start_time": appointment.start_time.isoformat(),
                "end_time": appointment.end_time.isoformat(),
                "timezone": user.timezone or "UTC",
            }

            success = await async_update_event(
                google_service,
                appointment.google_calendar_event_id,
                event_data,
            )
            google_sync_result = {"synced": success}

            if success:
                appointment.last_synced_at = datetime.utcnow()
                db.commit()

    result = {
        "success": True,
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat(),
        "end": appointment.end_time.isoformat(),
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }
    result["google_sync"] = google_sync_result

    return result


async def _cancel_appointment(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Cancel an existing appointment."""
    appointment_id = arguments.get("appointment_id")
    confirm = arguments.get("confirm", False)

    if not appointment_id:
        return {"error": "Missing appointment_id"}

    if not confirm:
        return {"error": "Cancellation not confirmed"}

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.user_id == user.id,
    ).first()

    if not appointment:
        return {"error": "Appointment not found"}

    appointment.status = "cancelled"
    db.commit()

    # Two-way sync: Delete from Google Calendar if event was synced
    google_sync_result = {"synced": False}
    if appointment.google_calendar_event_id:
        google_service = GoogleCalendarService(user, db)
        if google_service.is_connected():
            success = await async_delete_event(
                google_service,
                appointment.google_calendar_event_id,
            )
            google_sync_result = {"synced": success, "deleted": success}

            if success:
                appointment.google_calendar_event_id = None
                db.commit()

    result = {
        "success": True,
        "id": appointment.id,
        "title": appointment.title,
        "message": "Appointment cancelled",
    }
    result["google_sync"] = google_sync_result

    return result


async def _get_user_profile(user: User, db: Session) -> Dict[str, Any]:
    """Get user profile and preferences."""
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "timezone": user.timezone or "UTC",
        "locale": user.locale or "en",
    }


async def _set_user_preferences(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Update user preferences."""
    prefs = user.preferences
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)

    # Update fields if provided
    if "preferred_earliest_time" in arguments:
        time_str = arguments["preferred_earliest_time"]
        hour, minute = map(int, time_str.split(":"))
        from datetime import time
        prefs.preferred_earliest_time = time(hour, minute)
    if "preferred_latest_time" in arguments:
        time_str = arguments["preferred_latest_time"]
        hour, minute = map(int, time_str.split(":"))
        from datetime import time
        prefs.preferred_latest_time = time(hour, minute)
    if "avoid_lunch" in arguments:
        prefs.avoid_lunch = arguments["avoid_lunch"]
    if "min_break_minutes" in arguments:
        prefs.min_break_minutes = arguments["min_break_minutes"]
    if "preferred_duration_minutes" in arguments:
        prefs.preferred_duration_minutes = arguments["preferred_duration_minutes"]

    db.commit()

    return {
        "success": True,
        "message": "Preferences updated",
    }


async def _get_calendar(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Get calendar appointments."""
    start_date_str = arguments.get("start_date")
    end_date_str = arguments.get("end_date")

    query = db.query(Appointment).filter(
        Appointment.user_id == user.id,
        Appointment.status != "cancelled",
    )

    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        query = query.filter(Appointment.start_time >= start_date)
    if end_date_str:
        end_date = datetime.fromisoformat(end_date_str)
        query = query.filter(Appointment.start_time <= end_date)

    appointments = query.order_by(Appointment.start_time).all()

    return {
        "appointments": [
            {
                "id": appt.id,
                "title": appt.title,
                "description": appt.description,
                "start_time": appt.start_time.isoformat(),
                "end_time": appt.end_time.isoformat(),
                "duration_minutes": appt.duration_minutes,
                "status": appt.status,
            }
            for appt in appointments
        ],
        "total": len(appointments),
    }


async def _sync_to_google(user: User, db: Session) -> Dict[str, Any]:
    """Sync local appointments to Google Calendar."""
    if not is_google_connected(user.id, db):
        return {
            "success": False,
            "error": "Google Calendar is not connected. Please connect it in Settings.",
        }

    result = await sync_user_to_google(user.id, db)

    return {
        "success": result["success"],
        "message": f"Synced {result.get('synced_count', 0)} appointments to Google Calendar",
        "errors": result.get("errors", []),
    }


async def _sync_from_google(user: User, db: Session) -> Dict[str, Any]:
    """Sync events from Google Calendar to app."""
    if not is_google_connected(user.id, db):
        return {
            "success": False,
            "error": "Google Calendar is not connected. Please connect it in Settings.",
        }

    result = await sync_user_from_google(user.id, db)

    return {
        "success": result["success"],
        "message": f"Created {result.get('created_count', 0)} and updated {result.get('updated_count', 0)} appointments from Google Calendar",
        "total_google_events": result.get("total_google_events", 0),
    }


async def _create_recurring_appointment(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Create a recurring series of appointments."""
    import uuid
    from datetime import date as date_type
    from app.scheduling.engine import expand_recurrence

    title = arguments.get("title", "Recurring Appointment")
    description = arguments.get("description", "")
    start_time_str = arguments.get("start_time")
    duration = arguments.get("duration_minutes", 60)
    recurrence_rule = arguments.get("recurrence_rule")  # "daily", "weekly", "monthly"
    recurrence_end_str = arguments.get("recurrence_end_date")
    interval = arguments.get("interval", 1)

    if not start_time_str:
        return {"error": "Missing start_time"}
    if not recurrence_rule:
        return {"error": "Missing recurrence_rule (daily, weekly, or monthly)"}
    if not recurrence_end_str:
        return {"error": "Missing recurrence_end_date"}

    # Parse start time
    start_dt = datetime.fromisoformat(start_time_str)
    start_date = start_dt.date()

    # Parse recurrence end date
    recurrence_end = date_type.fromisoformat(recurrence_end_str)

    # Expand recurrence into dates
    occurrence_dates = expand_recurrence(
        recurrence_rule=recurrence_rule,
        start_date=start_date,
        duration_minutes=duration,
        range_end=recurrence_end,
        interval=interval,
    )

    if not occurrence_dates:
        return {"error": "No occurrences generated from recurrence rule"}

    # Create series ID
    series_id = str(uuid.uuid4())

    # Create appointments for each occurrence
    created_appointments = []
    conflicts = []

    for occ_date in occurrence_dates:
        # Calculate start and end times for this occurrence
        occ_start = datetime.combine(occ_date, start_dt.time())
        if start_dt.tzinfo:
            occ_start = occ_start.replace(tzinfo=start_dt.tzinfo)
        occ_end = occ_start + timedelta(minutes=duration)

        # Check for conflicts
        existing_appts = db.query(Appointment).filter(
            Appointment.user_id == user.id,
            Appointment.status != "cancelled",
        ).all()

        has_conflict = False
        for appt in existing_appts:
            appt_start = appt.start_time.replace(tzinfo=None) if appt.start_time.tzinfo else appt.start_time
            appt_end = appt.end_time.replace(tzinfo=None) if appt.end_time.tzinfo else appt.end_time
            occ_start_naive = occ_start.replace(tzinfo=None) if occ_start.tzinfo else occ_start
            occ_end_naive = occ_end.replace(tzinfo=None) if occ_end.tzinfo else occ_end

            if occ_start_naive < appt_end and occ_end_naive > appt_start:
                has_conflict = True
                conflicts.append({
                    "date": occ_date.isoformat(),
                    "conflicts_with": appt.title,
                })
                break

        if not has_conflict:
            appointment = Appointment(
                user_id=user.id,
                title=title,
                description=description,
                start_time=occ_start,
                end_time=occ_end,
                duration_minutes=duration,
                status="scheduled",
                recurrence_rule=recurrence_rule,
                series_id=series_id,
                parent_id=created_appointments[0].id if created_appointments else None,
            )
            db.add(appointment)
            created_appointments.append(appointment)

    db.commit()

    # Refresh all appointments to get IDs
    for appt in created_appointments:
        db.refresh(appt)

    result = {
        "success": True,
        "series_id": series_id,
        "recurrence_rule": recurrence_rule,
        "interval": interval,
        "recurrence_end": recurrence_end_str,
        "created_count": len(created_appointments),
        "skipped_count": len(conflicts),
        "conflicts": conflicts,
        "appointments": [
            {
                "id": appt.id,
                "start": appt.start_time.isoformat(),
                "end": appt.end_time.isoformat(),
            }
            for appt in created_appointments
        ],
    }

    return result


async def _cancel_recurring_series(
    arguments: Dict[str, Any],
    user: User,
    db: Session,
) -> Dict[str, Any]:
    """Cancel all appointments in a recurring series."""
    series_id = arguments.get("series_id")
    confirm = arguments.get("confirm", False)

    if not series_id:
        return {"error": "Missing series_id"}

    if not confirm:
        return {"error": "Cancellation not confirmed"}

    # Find all appointments in the series
    appointments = db.query(Appointment).filter(
        Appointment.user_id == user.id,
        Appointment.series_id == series_id,
        Appointment.status != "cancelled",
    ).all()

    if not appointments:
        return {"error": "No active appointments found in this series"}

    # Cancel all appointments
    cancelled_count = 0
    for appt in appointments:
        appt.status = "cancelled"
        cancelled_count += 1

    db.commit()

    return {
        "success": True,
        "series_id": series_id,
        "cancelled_count": cancelled_count,
        "message": f"Cancelled {cancelled_count} appointments in the series",
    }
