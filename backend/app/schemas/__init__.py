"""Pydantic schemas for the AI Appointment Scheduling Agent."""

from app.schemas.availability import AvailableSlot, AvailabilitySearchResponse
from app.schemas.appointment import AppointmentResponse, AppointmentListResponse, AvailableSlot as AvailSlot
from app.schemas.profile import ProfileResponse, PreferencesResponse, WorkingHoursResponse, FullProfileResponse, TimeRange, WorkingHoursDetail