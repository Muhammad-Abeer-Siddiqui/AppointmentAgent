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

    return {
        "success": True,
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat(),
        "end": appointment.end_time.isoformat(),
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }


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

    return {
        "success": True,
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat(),
        "end": appointment.end_time.isoformat(),
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }


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

    return {
        "success": True,
        "id": appointment.id,
        "title": appointment.title,
        "message": "Appointment cancelled",
    }


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
