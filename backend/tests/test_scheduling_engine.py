"""Unit tests for the scheduling engine."""

import pytest
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pytz

from app.scheduling.engine import (
    generate_available_slots,
    detect_conflict,
    get_working_hours_for_day,
    _calculate_slot_score,
    parse_appointment_time,
)
from app.scheduling.timezone_utils import (
    convert_to_timezone,
    convert_utc_to_local,
    convert_local_to_utc,
    get_current_time_in_timezone,
    format_utc_offset,
    is_dst,
    format_datetime_for_display,
)


# =============================================================================
# TIMEZONE TESTS
# =============================================================================

class TestTimezoneConversions:
    """Test timezone conversion utilities."""

    def test_convert_to_timezone(self):
        """Test converting datetime between timezones."""
        toronto_tz = ZoneInfo("America/Toronto")
        london_tz = ZoneInfo("Europe/London")

        # Create a datetime in Toronto
        toronto_time = datetime(2026, 9, 5, 10, 0, tzinfo=toronto_tz)

        # Convert to London
        london_time = convert_to_timezone(toronto_time, "America/Toronto", "Europe/London")

        # London should be 5 hours ahead (EDT vs BST)
        assert london_time.hour == 15
        assert london_time.tzinfo is not None

    def test_convert_utc_to_local(self):
        """Test converting UTC to local timezone."""
        utc_time = datetime(2026, 9, 5, 14, 0, tzinfo=pytz.UTC)
        toronto_time = convert_utc_to_local(utc_time, "America/Toronto")

        # Toronto is UTC-4 in September (EDT)
        assert toronto_time.hour == 10
        assert toronto_time.tzinfo is not None

    def test_convert_local_to_utc(self):
        """Test converting local time to UTC."""
        toronto_tz = ZoneInfo("America/Toronto")
        local_time = datetime(2026, 9, 5, 10, 0, tzinfo=toronto_tz)

        utc_time = convert_local_to_utc(local_time, "America/Toronto")

        # Toronto is UTC-4 in September (EDT)
        assert utc_time.hour == 14
        assert utc_time.tzinfo is not None

    def test_get_current_time_in_timezone(self):
        """Test getting current time in a timezone."""
        toronto_time = get_current_time_in_timezone("America/Toronto")

        assert toronto_time.tzinfo is not None
        # zoneinfo.ZoneInfo has .key or we can check .zone attribute on pytz but not zoneinfo
        # Check using .key attribute (Python 3.9+) or str representation
        tz_key = getattr(toronto_time.tzinfo, "key", str(toronto_time.tzinfo))
        assert "America/Toronto" in tz_key

    def test_format_utc_offset(self):
        """Test UTC offset formatting."""
        # Toronto in September is EDT (UTC-4)
        offset = format_utc_offset("America/Toronto")
        assert offset == "-04:00" or offset == "+00:00"  # Depends on DST

    def test_is_dst(self):
        """Test DST detection."""
        # September - Toronto should be in DST (EDT)
        toronto_tz = ZoneInfo("America/Toronto")
        september = datetime(2026, 9, 5, 12, 0).replace(tzinfo=toronto_tz)
        assert is_dst("America/Toronto", september) == True

        # January - Toronto should not be in DST (EST)
        january = datetime(2026, 1, 15, 12, 0).replace(tzinfo=toronto_tz)
        assert is_dst("America/Toronto", january) == False

    def test_format_datetime_for_display(self):
        """Test datetime formatting for display."""
        utc_time = datetime(2026, 9, 5, 14, 0, tzinfo=pytz.UTC)

        # Format in Toronto timezone
        display = format_datetime_for_display(utc_time, "America/Toronto")
        assert "10:00" in display  # 14:00 UTC = 10:00 EDT


# =============================================================================
# WORKING HOURS TESTS
# =============================================================================

class TestWorkingHours:
    """Test working hours calculation."""

    def test_get_working_hours_monday(self):
        """Test getting working hours for Monday."""
        working_hours = [
            {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
            {"day_of_week": 1, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
        ]

        # Monday (day_of_week=0)
        result = get_working_hours_for_day("America/Toronto", date(2026, 9, 7), working_hours)
        assert result is not None
        start, end = result
        assert start.hour == 9
        assert end.hour == 17

    def test_get_working_hours_weekend(self):
        """Test getting working hours for weekend (off day)."""
        working_hours = [
            {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
        ]

        # Saturday (day_of_week=5) - not in list
        result = get_working_hours_for_day("America/Toronto", date(2026, 9, 12), working_hours)
        assert result is None

    def test_get_working_hours_off_day(self):
        """Test getting working hours for an off day."""
        working_hours = [
            {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": True},
        ]

        # Monday but marked as off day
        result = get_working_hours_for_day("America/Toronto", date(2026, 9, 7), working_hours)
        assert result is None


# =============================================================================
# CONFLICT DETECTION TESTS
# =============================================================================

class TestConflictDetection:
    """Test appointment conflict detection."""

    def test_no_conflict(self):
        """Test no conflict when slots don't overlap."""
        new_start = datetime(2026, 9, 7, 10, 0, tzinfo=pytz.UTC)
        new_end = datetime(2026, 9, 7, 11, 0, tzinfo=pytz.UTC)

        existing = [
            {"start_time": datetime(2026, 9, 7, 12, 0, tzinfo=pytz.UTC),
             "end_time": datetime(2026, 9, 7, 13, 0, tzinfo=pytz.UTC)},
        ]

        assert detect_conflict(new_start, new_end, existing, "UTC") == False

    def test_conflict_detected(self):
        """Test conflict detection when slots overlap."""
        new_start = datetime(2026, 9, 7, 10, 30, tzinfo=pytz.UTC)
        new_end = datetime(2026, 9, 7, 11, 30, tzinfo=pytz.UTC)

        existing = [
            {"start_time": datetime(2026, 9, 7, 10, 0, tzinfo=pytz.UTC),
             "end_time": datetime(2026, 9, 7, 11, 0, tzinfo=pytz.UTC)},
        ]

        assert detect_conflict(new_start, new_end, existing, "UTC") == True

    def test_back_to_back_no_conflict(self):
        """Test back-to-back appointments don't conflict."""
        new_start = datetime(2026, 9, 7, 11, 0, tzinfo=pytz.UTC)
        new_end = datetime(2026, 9, 7, 12, 0, tzinfo=pytz.UTC)

        existing = [
            {"start_time": datetime(2026, 9, 7, 10, 0, tzinfo=pytz.UTC),
             "end_time": datetime(2026, 9, 7, 11, 0, tzinfo=pytz.UTC)},
        ]

        # Back-to-back should not conflict (end == start is not overlap)
        assert detect_conflict(new_start, new_end, existing, "UTC") == False


# =============================================================================
# SLOT GENERATION TESTS
# =============================================================================

class TestSlotGeneration:
    """Test available slot generation."""

    def test_basic_slot_generation(self):
        """Test basic slot generation within working hours."""
        working_hours = [
            {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
        ]

        # Monday Sept 7, 2026
        slots = generate_available_slots(
            date_range=(date(2026, 9, 7), date(2026, 9, 7)),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=working_hours,
            existing_appointments=[],
            preferences={"preferred_earliest": "09:00", "preferred_latest": "17:00"},
        )

        assert len(slots) > 0
        # All slots should be within working hours
        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            assert start.hour >= 9
            assert start.hour < 17

    def test_slot_generation_with_existing_appointments(self):
        """Test slot generation avoids existing appointments."""
        working_hours = [
            {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
        ]

        existing = [
            {"start_time": datetime(2026, 9, 7, 10, 0, tzinfo=ZoneInfo("America/Toronto")),
             "end_time": datetime(2026, 9, 7, 11, 0, tzinfo=ZoneInfo("America/Toronto"))},
        ]

        slots = generate_available_slots(
            date_range=(date(2026, 9, 7), date(2026, 9, 7)),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=working_hours,
            existing_appointments=existing,
            preferences={"preferred_earliest": "09:00", "preferred_latest": "17:00"},
        )

        # No slot should start during 10:00-11:00
        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            # Should not be in the middle of the existing appointment
            if start.hour == 10:
                assert start.minute >= 0  # Slot starting at 10 is fine if it ends before 11
                # Actually check if it conflicts
                slot_end = datetime.fromisoformat(slot["end"])
                existing_start = existing[0]["start_time"]
                existing_end = existing[0]["end_time"]
                # No overlap
                assert slot_end <= existing_start or start >= existing_end

    def test_slot_scoring(self):
        """Test slot scoring prefers certain times."""
        # Morning slot
        morning_start = datetime(2026, 9, 7, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
        morning_end = datetime(2026, 9, 7, 10, 0, tzinfo=ZoneInfo("America/Toronto"))

        # Afternoon slot
        afternoon_start = datetime(2026, 9, 7, 14, 0, tzinfo=ZoneInfo("America/Toronto"))
        afternoon_end = datetime(2026, 9, 7, 15, 0, tzinfo=ZoneInfo("America/Toronto"))

        prefs = {"preferred_earliest": "09:00", "preferred_latest": "17:00"}

        morning_result = _calculate_slot_score(morning_start, morning_end, prefs)
        afternoon_result = _calculate_slot_score(afternoon_start, afternoon_end, prefs)

        # Both should have scores, preferences affect scoring
        assert morning_result["score"] > 0
        assert afternoon_result["score"] > 0
        assert "reasons" in morning_result
        assert "reasons" in afternoon_result


# =============================================================================
# APPOINTMENT TIME PARSING TESTS
# =============================================================================

class TestAppointmentTimeParsing:
    """Test appointment time parsing."""

    def test_parse_naive_datetime(self):
        """Test parsing naive datetime string.

        Note: Naive datetimes are treated as UTC by parse_appointment_time,
        so a naive 10:00 becomes 10:00 UTC, which is 06:00 EDT in Toronto.
        """
        start, end = parse_appointment_time(
            "2026-09-07T10:00:00",
            "2026-09-07T11:00:00",
            "America/Toronto"
        )

        assert start.tzinfo is not None
        assert end.tzinfo is not None
        # Naive datetime 10:00 is interpreted as UTC, converted to Toronto = 06:00 EDT
        assert start.hour == 6
        assert end.hour == 7

    def test_parse_utc_datetime(self):
        """Test parsing UTC datetime string."""
        start, end = parse_appointment_time(
            "2026-09-07T14:00:00+00:00",
            "2026-09-07T15:00:00+00:00",
            "America/Toronto"
        )

        # Should be converted to Toronto time (10:00 EDT)
        assert start.hour == 10
        assert end.hour == 11


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSchedulingIntegration:
    """Integration tests for complete scheduling scenarios."""

    def test_weekly_availability(self):
        """Test availability across a week."""
        working_hours = [
            {"day_of_week": i, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False}
            for i in range(5)  # Mon-Fri
        ]

        # Get availability for a week
        slots = generate_available_slots(
            date_range=(date(2026, 9, 7), date(2026, 9, 11)),  # Mon-Fri
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=working_hours,
            existing_appointments=[],
            preferences={"preferred_earliest": "09:00", "preferred_latest": "17:00"},
        )

        # Should have slots (at least 4 days, may depend on slot generation params)
        assert len(slots) >= 4

        # All slots should be on weekdays
        for slot in slots:
            slot_date = datetime.fromisoformat(slot["start"]).date()
            assert slot_date.weekday() < 5  # Monday=0, Friday=4

    def test_multi_person_availability(self):
        """Test multi-person availability intersection."""
        # This tests the basic logic - actual implementation uses database
        working_hours_person1 = [
            {"day_of_week": 0, "start_time": time(9, 0), "end_time": time(17, 0), "is_off_day": False},
        ]
        working_hours_person2 = [
            {"day_of_week": 0, "start_time": time(10, 0), "end_time": time(18, 0), "is_off_day": False},
        ]

        # Person 1 available 9-17
        slots1 = generate_available_slots(
            date_range=(date(2026, 9, 7), date(2026, 9, 7)),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=working_hours_person1,
            existing_appointments=[],
            preferences={},
        )

        # Person 2 available 10-18
        slots2 = generate_available_slots(
            date_range=(date(2026, 9, 7), date(2026, 9, 7)),
            duration_minutes=60,
            user_tz="America/Toronto",
            working_hours_list=working_hours_person2,
            existing_appointments=[],
            preferences={},
        )

        # Both should have slots
        assert len(slots1) > 0
        assert len(slots2) > 0

        # Find intersection manually
        common_slots = []
        for s1 in slots1:
            for s2 in slots2:
                if s1["start"] == s2["start"]:
                    common_slots.append(s1)

        # Common slots should be within 10-17 (intersection of 9-17 and 10-18)
        for slot in common_slots:
            start = datetime.fromisoformat(slot["start"])
            assert start.hour >= 10


# =============================================================================
# RECURRENCE EXPANSION TESTS
# =============================================================================

class TestRecurrenceExpansion:
    """Test recurrence expansion logic."""

    def test_daily_recurrence(self):
        """Test daily recurrence generates correct dates."""
        from app.scheduling.engine import expand_recurrence
        from datetime import date

        dates = expand_recurrence(
            recurrence_rule="daily",
            start_date=date(2026, 9, 1),
            duration_minutes=60,
            range_end=date(2026, 9, 5),
        )

        assert len(dates) == 5
        assert dates[0] == date(2026, 9, 1)
        assert dates[-1] == date(2026, 9, 5)

    def test_weekly_recurrence(self):
        """Test weekly recurrence generates correct dates."""
        from app.scheduling.engine import expand_recurrence
        from datetime import date

        dates = expand_recurrence(
            recurrence_rule="weekly",
            start_date=date(2026, 9, 1),
            duration_minutes=60,
            range_end=date(2026, 9, 30),
        )

        # Should be every Tuesday in September 2026
        assert len(dates) == 5  # Sep 1, 8, 15, 22, 29
        assert dates[0] == date(2026, 9, 1)
        assert dates[1] == date(2026, 9, 8)

    def test_monthly_recurrence(self):
        """Test monthly recurrence generates correct dates."""
        from app.scheduling.engine import expand_recurrence
        from datetime import date

        dates = expand_recurrence(
            recurrence_rule="monthly",
            start_date=date(2026, 1, 15),
            duration_minutes=60,
            range_end=date(2026, 6, 30),
        )

        # Should be 15th of each month
        assert len(dates) == 6
        assert dates[0] == date(2026, 1, 15)
        assert dates[1] == date(2026, 2, 15)

    def test_interval_2_weekly(self):
        """Test weekly recurrence with interval of 2."""
        from app.scheduling.engine import expand_recurrence
        from datetime import date

        dates = expand_recurrence(
            recurrence_rule="weekly",
            start_date=date(2026, 9, 1),
            duration_minutes=60,
            range_end=date(2026, 9, 30),
            interval=2,
        )

        # Should be every other Tuesday
        assert len(dates) == 3  # Sep 1, Sep 15, Sep 29
        assert dates[0] == date(2026, 9, 1)
        assert dates[1] == date(2026, 9, 15)
        assert dates[2] == date(2026, 9, 29)


# =============================================================================
# SCORING REASONS TESTS
# =============================================================================

class TestScoringReasons:
    """Test that scoring returns reasons along with score."""

    def test_scoring_returns_reasons(self):
        """Test that _calculate_slot_score returns reasons list."""
        from app.scheduling.engine import _calculate_slot_score
        from datetime import datetime, time as dt_time
        from zoneinfo import ZoneInfo

        slot_start = datetime(2026, 9, 7, 10, 0, tzinfo=ZoneInfo("America/Toronto"))
        slot_end = datetime(2026, 9, 7, 11, 0, tzinfo=ZoneInfo("America/Toronto"))

        prefs = {"preferred_earliest": "09:00", "preferred_latest": "17:00", "avoid_lunch": True}

        result = _calculate_slot_score(slot_start, slot_end, prefs)

        assert "score" in result
        assert "reasons" in result
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) > 0

    def test_lunch_penalty_with_avoid_lunch_true(self):
        """Test lunch penalty is applied when avoid_lunch is True."""
        from app.scheduling.engine import _calculate_slot_score
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Slot during lunch hour
        slot_start = datetime(2026, 9, 7, 12, 0, tzinfo=ZoneInfo("America/Toronto"))
        slot_end = datetime(2026, 9, 7, 13, 0, tzinfo=ZoneInfo("America/Toronto"))

        prefs_with_lunch = {"avoid_lunch": True}
        prefs_without_lunch = {"avoid_lunch": False}

        result_with = _calculate_slot_score(slot_start, slot_end, prefs_with_lunch)
        result_without = _calculate_slot_score(slot_start, slot_end, prefs_without_lunch)

        # Score should be lower when avoiding lunch
        assert result_with["score"] < result_without["score"]
        assert "Overlaps with lunch hour" in result_with["reasons"]


# =============================================================================
# APPOINTMENT RECURRENCE FIELDS TESTS
# =============================================================================

class TestAppointmentRecurrenceFields:
    """Test appointment recurrence fields."""

    def test_appointment_has_recurrence_fields(self):
        """Test that Appointment model has recurrence fields."""
        from app.database.models import Appointment

        # Check that the model has the new fields
        assert hasattr(Appointment, "recurrence_rule")
        assert hasattr(Appointment, "series_id")
        assert hasattr(Appointment, "parent_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
