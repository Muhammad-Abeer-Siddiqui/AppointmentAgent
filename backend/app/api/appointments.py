"""Appointment API routes for the AI Appointment Scheduling Agent."""

from fastapi import APIRouter, Depends, Body, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, time as dt_time

from app.database import get_db_session
from app.database.models import Appointment, User
from app.schemas.appointment import AppointmentResponse
from app.auth import get_current_user


router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("/", response_model=None)
async def get_appointments(
    start_date: Optional[str] = Query(
        None, description="Start date ISO, e.g. '2026-09-01'"
    ),
    end_date: Optional[str] = Query(
        None, description="End date ISO, e.g. '2026-09-30'"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get user's appointments within a date range."""
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

    result = [
        {
            "id": apt.id,
            "title": apt.title,
            "description": apt.description,
            "start": apt.start_time.isoformat() if apt.start_time else None,
            "end": apt.end_time.isoformat() if apt.end_time else None,
            "duration_minutes": apt.duration_minutes,
            "status": apt.status,
        }
        for apt in appointments
    ]

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


@router.delete("/{appointment_id}", response_model=None)
async def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Cancel an appointment."""
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404, detail="Appointment not found"
        )

    appointment.status = "cancelled"
    db.commit()

    return {
        "message": "Appointment cancelled successfully",
        "id": appointment.id,
    }


@router.get("/{appointment_id}", response_model=None)
async def get_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a single appointment by ID."""
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404, detail="Appointment not found"
        )

    return {
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat() if appointment.start_time else None,
        "end": appointment.end_time.isoformat() if appointment.end_time else None,
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }


@router.patch("/{appointment_id}", response_model=None)
async def update_appointment(
    appointment_id: int,
    title: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    start_time: Optional[str] = Body(None),
    end_time: Optional[str] = Body(None),
    duration_minutes: Optional[int] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update an existing appointment."""
    from datetime import datetime as dt

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404, detail="Appointment not found"
        )

    if title is not None:
        appointment.title = title
    if description is not None:
        appointment.description = description
    if start_time is not None:
        appointment.start_time = dt.fromisoformat(start_time)
    if end_time is not None:
        appointment.end_time = dt.fromisoformat(end_time)
    if duration_minutes is not None:
        appointment.duration_minutes = duration_minutes

    db.commit()
    db.refresh(appointment)

    return {
        "id": appointment.id,
        "title": appointment.title,
        "description": appointment.description,
        "start": appointment.start_time.isoformat() if appointment.start_time else None,
        "end": appointment.end_time.isoformat() if appointment.end_time else None,
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
    }


@router.delete("/series/{series_id}", response_model=None)
async def cancel_recurring_series(
    series_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Cancel all appointments in a recurring series."""
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.series_id == series_id,
            Appointment.user_id == current_user.id,
            Appointment.status != "cancelled",
        )
        .all()
    )

    if not appointments:
        raise HTTPException(
            status_code=404, detail="No active appointments found in this series"
        )

    cancelled_count = 0
    for appointment in appointments:
        appointment.status = "cancelled"
        cancelled_count += 1

    db.commit()

    return {
        "success": True,
        "series_id": series_id,
        "cancelled_count": cancelled_count,
        "message": f"Cancelled {cancelled_count} appointments in the series",
    }
