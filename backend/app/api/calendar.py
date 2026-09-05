"""Calendar API routes for the AI Appointment Scheduling Agent."""

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, date, time as dt_time

from app.database import get_db_session
from app.database.models import User, Appointment
from app.auth import get_current_user


router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/", response_model=None)
async def get_calendar(
    start_date: Optional[str] = Query(
        None, description="ISO date string, e.g. '2026-09-10'"
    ),
    end_date: Optional[str] = Query(
        None, description="ISO date string"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get user's calendar appointments within a date range."""
    query = db.query(Appointment).filter(Appointment.user_id == current_user.id)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Appointment.start_time >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Appointment.start_time <= end_dt)
        except ValueError:
            pass

    appointments = query.order_by(Appointment.start_time).all()

    result = []
    for apt in appointments:
        result.append(
            {
                "id": apt.id,
                "title": apt.title,
                "description": apt.description,
                "start": apt.start_time.isoformat()
                if apt.start_time
                else None,
                "end": apt.end_time.isoformat() if apt.end_time else None,
                "duration_minutes": apt.duration_minutes,
                "status": apt.status,
            }
        )

    return {"appointments": result}


@router.post("/", response_model=None)
async def create_appointment(
    title: str = Body(...),
    description: Optional[str] = Body(None),
    start_time: str = Body(
        ..., description="ISO format datetime, e.g. '2026-09-10T14:00:00'"
    ),
    end_time: str = Body(
        ..., description="ISO format datetime, e.g. '2026-09-10T15:00:00'"
    ),
    duration_minutes: int = Body(
        ..., description="Duration in minutes"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create a new appointment."""
    from datetime import datetime as dt

    start_dt = dt.fromisoformat(start_time)
    end_dt = dt.fromisoformat(end_time)

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