"""Pydantic schemas for user profile and preferences responses."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class TimeRange(BaseModel):
    """A time range with start and end."""
    start: datetime
    end: datetime


class WorkingHoursResponse(BaseModel):
    """Response for a single day's working hours."""
    start: str
    end: str
    is_off_day: bool


class PreferencesResponse(BaseModel):
    """Response for user preferences."""
    preferred_earliest_time: str
    preferred_latest_time: str
    avoid_lunch: bool
    min_break_minutes: int
    preferred_duration_minutes: int


class ProfileResponse(BaseModel):
    """Response for user profile."""
    id: int
    name: Optional[str] = None
    email: str
    timezone: str
    locale: str


class WorkingHoursDetail(BaseModel):
    """Detail for a single working hours entry."""
    start: str
    end: str
    is_off_day: bool


class FullProfileResponse(BaseModel):
    """Complete profile response with preferences and working hours."""
    profile: ProfileResponse
    preferences: PreferencesResponse
    working_hours: Dict[str, WorkingHoursDetail]


class WorkingHoursUpdate(BaseModel):
    """Request body for updating working hours (batch update)."""
    day_of_week: int
    start_time: str
    end_time: str
    is_off_day: bool = False


class WorkingHoursBatchUpdate(BaseModel):
    """Batch update for working hours."""
    working_hours: List[WorkingHoursUpdate]


class SyncDirectionRequest(BaseModel):
    """Request body for sync direction."""
    direction: str