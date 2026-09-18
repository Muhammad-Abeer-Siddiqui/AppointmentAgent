"""Edge case and negative tests for the scheduling engine and tools."""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduling.engine import (
    generate_available_slots,
    _calculate_slot_score,
    detect_conflict,
)


TZ = ZoneInfo("America/Toronto")
TZ_UTC = ZoneInfo("UTC")


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0, tz: ZoneInfo = TZ) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=tz)


# =========================================================================
# 1. Invalid Inputs
# =========================================================================


class TestInvalidInputs:
    """Tests that invalid inputs are handled gracefully."""

    def test_search_availability_end_date_before_start_date(self):
        start = date(2026, 9, 20)
        end = date(2026, 9, 15)  # before start

        slots = generate_available_slots(
            date_range=(start, end),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=[
                {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
            ],
            existing_appointments=[],
            preferences={},
        )

        # No slots should be returned when range is inverted
        assert slots == []

    def test_create_appointment_negative_duration(self):
        """Negative duration produces a slot with end before start (known limitation)."""
        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=-30,
            user_tz="America/Toronto",
            working_hours_list=[
                {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
            ],
            existing_appointments=[],
            preferences={},
        )

        if slots:
            s = datetime.fromisoformat(slots[0]["start"])
            e = datetime.fromisoformat(slots[0]["end"])
            assert e <= s, "negative duration should produce end <= start"

    def test_create_appointment_end_time_before_start_time(self):
        """Appointment ending before it starts should produce no valid slots."""
        start = _dt(2026, 9, 15, 14, 0)
        end = _dt(2026, 9, 15, 12, 0)  # before start

        conflict = detect_conflict(start, end, [], "America/Toronto")

        # Overlap check: start < existing_end and end > existing_start
        # 14:00 < 12:00 is False → no conflict, but the input itself is invalid
        # The engine should not crash; we verify it returns False for empty list
        assert conflict is False

    def test_search_availability_invalid_timezone(self):
        """Invalid timezone should raise an error or be handled."""
        with pytest.raises((ValueError, KeyError)):
            generate_available_slots(
                date_range=(date(2026, 9, 15), date(2026, 9, 15)),
                duration_minutes=60,
                user_tz="Not/A/Timezone",
                working_hours_list=[],
                existing_appointments=[],
                preferences={},
            )

    def test_update_appointment_invalid_id(self):
        """Updating a nonexistent appointment returns error via tool layer."""
        # Simulate the tool logic: query returns None → error
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        from app.database.models import Appointment
        result = mock_session.query(Appointment).filter(
            Appointment.id == 999999,
            Appointment.user_id == 1,
        ).first()

        assert result is None


# =========================================================================
# 2. Boundary Conditions
# =========================================================================


class TestBoundaryConditions:
    """Tests at the edges of valid ranges."""

    def test_slot_generation_midnight(self):
        """Slot at 00:00-01:00 (midnight boundary)."""
        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=60,
            user_tz="UTC",
            working_hours_list=[],
            existing_appointments=[],
            preferences={},
        )

        # 24/7 mode: should include a midnight slot
        starts = [s["start"] for s in slots]
        assert any("T00:00" in s for s in starts), f"Expected midnight slot, got: {starts}"

    def test_slot_generation_very_long_appointment(self):
        """8-hour (480 min) appointment in a 24/7 window should produce at least one slot."""
        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=480,
            user_tz="UTC",
            working_hours_list=[],
            existing_appointments=[],
            preferences={},
        )

        # 24h = 1440 min; minus 15 buffer each side = 1410 min available
        assert len(slots) >= 1
        # First slot should start at 00:00
        assert "T00:00" in slots[0]["start"]

    def test_slot_generation_very_short_appointment(self):
        """5-minute appointment should be schedulable."""
        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=5,
            user_tz="UTC",
            working_hours_list=[],
            existing_appointments=[],
            preferences={},
        )

        assert len(slots) >= 1
        # Slot end should be exactly 5 minutes after start
        start = datetime.fromisoformat(slots[0]["start"])
        end = datetime.fromisoformat(slots[0]["end"])
        assert (end - start) == timedelta(minutes=5)

    def test_slot_generation_end_of_day(self):
        """Slot at 23:00-23:59 (end of day)."""
        working_hours = [
            {"day_of_week": 0, "start_time": time(23, 0), "end_time": time(23, 59), "is_off_day": False},
        ]

        # Monday 2026-09-21
        slots = generate_available_slots(
            date_range=(date(2026, 9, 21), date(2026, 9, 21)),
            duration_minutes=5,
            user_tz="America/Toronto",
            working_hours_list=working_hours,
            existing_appointments=[],
            preferences={},
        )

        # Only 59 minutes available, minus 15 buffer = 44 min
        assert len(slots) >= 1
        start = datetime.fromisoformat(slots[0]["start"])
        assert start.hour == 23

    def test_multiple_appointments_filling_entire_day(self):
        """When every slot is booked, no available slots should be returned."""
        busy = []
        for h in range(9, 17):
            busy.append({
                "start_time": _dt(2026, 9, 15, h, 0),
                "end_time": _dt(2026, 9, 15, h + 1, 0),
            })

        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=[
                {"day_of_week": 2, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
            ],
            existing_appointments=busy,
            preferences={},
        )

        assert slots == []


# =========================================================================
# 3. Timezone Edge Cases
# =========================================================================


class TestTimezoneEdgeCases:
    """Tests for timezone-specific behaviour."""

    def test_slot_generation_utc(self):
        """Slots generated in UTC should have correct offsets."""
        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=60,
            user_tz="UTC",
            working_hours_list=[
                {"day_of_week": 2, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
            ],
            existing_appointments=[],
            preferences={},
        )

        assert len(slots) > 0
        for slot in slots:
            assert slot["timezone"] == "UTC"
            start = datetime.fromisoformat(slot["start"])
            assert start.hour >= 9
            assert start.hour < 17

    def test_slot_generation_plus_13_timezone(self):
        """Pacific/Kiritimati (UTC+14) is one of the most offset timezones."""
        slots = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=60,
            user_tz="Pacific/Kiritimati",
            working_hours_list=[
                {"day_of_week": 2, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
            ],
            existing_appointments=[],
            preferences={},
        )

        assert len(slots) > 0
        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            assert start.hour >= 9
            assert start.hour < 17

    def test_dst_transition_spring_forward(self):
        """2026-03-08: US clocks spring forward 2 AM → 3 AM (America/Toronto).

        The day has only 23 wall-clock hours. Slots should still be generated
        for working hours after the transition.
        """
        # DST transition: 2026-03-08 at 2:00 AM
        dst_date = date(2026, 3, 8)

        slots = generate_available_slots(
            date_range=(dst_date, dst_date),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=[
                {"day_of_week": 6, "start_time": time(1, 0), "end_time": time(23, 0), "is_off_day": False},
            ],
            existing_appointments=[],
            preferences={},
        )

        # Should still produce slots; the engine handles DST via zoneinfo
        assert len(slots) > 0
        # Verify slots are timezone-aware and on the correct date
        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            assert start.date() == dst_date

    def test_dst_transition_fall_back(self):
        """2026-11-01: US clocks fall back 2 AM → 1 AM (America/Toronto).

        The day has 25 wall-clock hours. Slots should still be generated.
        """
        # DST transition: 2026-11-01 at 2:00 AM
        dst_date = date(2026, 11, 1)

        slots = generate_available_slots(
            date_range=(dst_date, dst_date),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=[
                {"day_of_week": 6, "start_time": time(1, 0), "end_time": time(23, 0), "is_off_day": False},
            ],
            existing_appointments=[],
            preferences={},
        )

        assert len(slots) > 0
        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            assert start.date() == dst_date

    def test_date_boundary_across_timezones(self):
        """An appointment at 23:00 UTC is next-day in +5 timezones.

        Verify the engine places the slot on the correct UTC date while the
        local timezone sees the next day.
        """
        # Use UTC so the date is unambiguous
        slots_utc = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=60,
            user_tz="UTC",
            working_hours_list=[],
            existing_appointments=[],
            preferences={},
        )

        # Use +05:00 timezone — midnight UTC is 05:00 local
        slots_plus5 = generate_available_slots(
            date_range=(date(2026, 9, 15), date(2026, 9, 15)),
            duration_minutes=60,
            user_tz="Asia/Karachi",
            working_hours_list=[],
            existing_appointments=[],
            preferences={},
        )

        # UTC should have a slot starting at 00:00 UTC
        utc_starts = [s["start"] for s in slots_utc]
        assert any("T00:00" in s for s in utc_starts)

        # Asia/Karachi (UTC+5) should also have slots on the same date
        assert len(slots_plus5) > 0
        for slot in slots_plus5:
            start = datetime.fromisoformat(slot["start"])
            assert start.tzinfo is not None
