"""Pydantic schemas for availability API responses."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class AvailableSlot(BaseModel):
    """A single available time slot."""
    start: datetime
    end: datetime
    score: int
    date: str
    timezone: str = "UTC"


class AvailabilitySearchResponse(BaseModel):
    """Response for availability search."""
    slots: List[AvailableSlot]
    duration_minutes: int
    date_range: Dict[str, str]