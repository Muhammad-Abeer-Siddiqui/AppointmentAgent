"""Pydantic schemas for appointment API responses."""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class AvailableSlot(BaseModel):
    """A single available time slot."""
    start: datetime
    end: datetime
    score: int
    date: str
    timezone: str = "UTC"


class AppointmentResponse(BaseModel):
    """Response for a single appointment."""
    id: int
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    duration_minutes: int
    status: str


class AppointmentListResponse(BaseModel):
    """Response listing multiple appointments."""
    appointments: List[AppointmentResponse]


class CalendarOverviewResponse(BaseModel):
    """Response for calendar overview."""
    total_appointments: int
    appointments: List[AppointmentResponse]