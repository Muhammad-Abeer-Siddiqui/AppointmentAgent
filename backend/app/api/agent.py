"""Agent API routes for the AI Appointment Scheduling Agent.

This module provides the tool-using agent interface where the LLM can call
validated backend functions to perform scheduling operations. The LLM never
directly accesses the database - it always goes through these validated endpoints.
"""

from fastapi import APIRouter, Depends, Body, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, date

from app.database import get_db_session
from app.database.models import User, Appointment, AvailabilityRule
from app.schemas.appointment import AppointmentResponse
from app.auth import get_current_user
from app.scheduling.engine import (
    generate_available_slots,
    find_multi_person_availability,
    to_utc,
    from_utc,
    localize_naive,
    detect_conflict,
    parse_appointment_time,
    _calculate_slot_score,
)


router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/search-availability", response_model=None)
async def agent_search_availability(
    duration_minutes: int = Body(
        ..., description="Required duration in minutes"
    ),
    start_date: str = Body(
        ..., description="Start date ISO, e.g. '2026-09-09'"
    ),
    end_date: str = Body(
        ..., description="End date ISO, e.g. '2026-09-15'"
    ),
    user_tz: str = Body(
        ..., description="User's IANA timezone, e.g. 'America/Toronto'"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Search for available time slots (agent-assisted).

    This endpoint is designed to be called by the AI agent. It uses the
    deterministic scheduling engine to generate available slots based on
    the user's working hours, existing appointments, and preferences.
    """
    from app.database.models import UserPreferences as UP

    # Get user preferences
    prefs = current_user.preferences
    if not prefs:
        from app.database.models import UserPreferences
        prefs = UP(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    # Get working hours (convert to dicts for engine)
    wh_list = [
        {
            "day_of_week": wh.day_of_week,
            "start_time": wh.start_time,
            "end_time": wh.end_time,
            "is_off_day": wh.is_off_day,
        }
        for wh in current_user.working_hours
    ]

    # Get existing appointments
    existing_appts = db.query(Appointment).filter(
        Appointment.user_id == current_user.id,
        Appointment.status != "cancelled",
    ).all()

    # Convert appointments to dict format for engine
    appt_dicts = [
        {
            "start_time": appt.start_time,
            "end_time": appt.end_time,
        }
        for appt in existing_appts
    ]

    # Generate available slots using deterministic engine
    slots = generate_available_slots(
        date_range=(
            datetime.fromisoformat(start_date).date(),
            datetime.fromisoformat(end_date).date(),
        ),
        duration_minutes=duration_minutes,
        user_tz=user_tz,
        working_hours_list=wh_list,
        existing_appointments=appt_dicts,
        preferences={
            "preferred_earliest": prefs.preferred_earliest_time.strftime("%H:%M") if prefs.preferred_earliest_time else "09:00",
            "preferred_latest": prefs.preferred_latest_time.strftime("%H:%M") if prefs.preferred_latest_time else "17:00",
            "avoid_lunch": prefs.avoid_lunch,
            "min_break_minutes": prefs.min_break_minutes,
        },
    )

    available_slots = [
        {
            "id": i,
            "start": slot.get("start", ""),
            "end": slot.get("end", ""),
            "score": slot.get("score", 50),
        }
        for i, slot in enumerate(slots[:20])
    ]

    return {
        "slots": available_slots,
        "duration_minutes": duration_minutes,
        "user_tz": user_tz,
        "date_range": {
            "start": start_date,
            "end": end_date,
        },
    }


@router.post("/multi-person-availability", response_model=None)
async def agent_multi_person_availability(
    attendee_ids: List[int] = Body(
        ..., description="List of user IDs to find common availability for"
    ),
    duration_minutes: int = Body(
        ..., description="Required duration in minutes"
    ),
    start_date: str = Body(
        ..., description="Start date ISO, e.g. '2026-09-09'"
    ),
    end_date: str = Body(
        ..., description="End date ISO, e.g. '2026-09-15'"
    ),
    user_tz: str = Body(
        ..., description="Primary user's IANA timezone"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Find time slots when ALL attendees are available.

    This is the multi-person scheduling endpoint. It calculates the
    intersection of availability across multiple users' calendars.
    """
    from app.database.models import UserPreferences as UP

    # Get attendee data
    attendees = []
    for attendee_id in attendee_ids:
        attendee = db.query(User).get(attendee_id)
        if attendee:
            prefs = attendee.preferences
            if not prefs:
                from app.database.models import UserPreferences
                prefs = UP(user_id=attendee.id)
                db.add(prefs)
                db.commit()
                db.refresh(prefs)

            wh = attendee.working_hours or []

            stmt = db.query(Appointment).filter(
                Appointment.user_id == attendee_id,
                Appointment.status != "cancelled",
            ).all()
            appts = stmt if stmt else []

            attendees.append(
                {
                    "id": attendee.id,
                    "name": attendee.name,
                    "email": attendee.email,
                    "timezone": attendee.timezone or user_tz,
                    "preferences": prefs,
                    "working_hours": wh,
                    "appointments": [
                        {
                            "start_time": appt.start_time,
                            "end_time": appt.end_time,
                        }
                        for appt in appts
                    ],
                }
            )

    if len(attendees) < 2:
        return {
            "slots": [],
            "message": "Need at least 2 attendees for multi-person scheduling",
        }

    # Use the engine to find multi-person availability
    slots = find_multi_person_availability(
        attendee_ids=attendee_ids,
        date_range=(
            datetime.fromisoformat(start_date).date(),
            datetime.fromisoformat(end_date).date(),
        ),
        duration_minutes=duration_minutes,
        user_tz=user_tz,
        db_session=db,
    )

    available_slots = [
        {
            "id": i,
            "start": slot.get("start", ""),
            "end": slot.get("end", ""),
            "score": slot.get("score", 50),
        }
        for i, slot in enumerate(slots[:15])
    ]

    return {
        "slots": available_slots,
        "duration_minutes": duration_minutes,
        "user_tz": user_tz,
        "date_range": {
            "start": start_date,
            "end": end_date,
        },
    }


@router.post("/create-appointment", response_model=None)
async def agent_create_appointment(
    title: str = Body(..., description="Appointment title"),
    description: Optional[str] = Body(
        None, description="Appointment description"
    ),
    start_time: str = Body(
        ..., description="ISO format datetime start"
    ),
    end_time: str = Body(
        ..., description="ISO format datetime end"
    ),
    duration_minutes: int = Body(
        ..., description="Duration in minutes"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create an appointment through the agent endpoint.

    This validates and creates an appointment using the deterministic
    scheduling engine, ensuring no conflicts with existing appointments.
    """
    from datetime import datetime as dt

    start_dt = dt.fromisoformat(start_time)
    end_dt = dt.fromisoformat(end_time)

    # Check for conflicts with existing appointments
    existing_appts = db.query(Appointment).filter(
        Appointment.user_id == current_user.id,
        Appointment.status != "cancelled",
    ).all()

    # Convert to UTC for comparison
    start_utc = to_utc(start_dt)
    end_utc = to_utc(end_dt)

    for appt in existing_appts:
        appt_start_utc = to_utc(appt.start_time)
        appt_end_utc = to_utc(appt.end_time)

        # Check overlap
        if start_utc < appt_end_utc and end_utc > appt_start_utc:
            raise HTTPException(
                status_code=409,
                detail="Conflict with existing appointment",
            )

    # Create the appointment
    appointment = Appointment(
        user_id=current_user.id,
        title=title,
        description=description,
        start_time=start_dt,
        end_time=end_dt,
        duration_minutes=duration_minutes,
        status="scheduled",
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return {
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat(),
        "end": appointment.end_time.isoformat(),
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }
