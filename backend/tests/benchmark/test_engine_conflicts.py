"""Tests for detect_conflict in app.scheduling.engine."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.scheduling.engine import detect_conflict

TZ = ZoneInfo("America/Toronto")


def _make_appt(start: datetime, end: datetime) -> dict:
    return {"start_time": start, "end_time": end}


# =============================================================================
# No Conflict
# =============================================================================


class TestNoConflict:
    def test_completely_separate_ranges(self):
        new_start = datetime(2025, 7, 1, 9, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 12, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False

    def test_back_to_back_appointments(self):
        new_start = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 11, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 8, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False

    def test_new_before_all_existing(self):
        new_start = datetime(2025, 7, 1, 7, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 8, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 9, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
            ),
            _make_appt(
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 12, 0, tzinfo=TZ),
            ),
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False

    def test_new_after_all_existing(self):
        new_start = datetime(2025, 7, 1, 14, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 15, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 8, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 9, 0, tzinfo=TZ),
            ),
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            ),
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False


# =============================================================================
# Direct Conflicts
# =============================================================================


class TestDirectConflicts:
    def test_exact_overlap(self):
        start = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        end = datetime(2025, 7, 1, 11, 0, tzinfo=TZ)
        existing = [_make_appt(start, end)]
        assert detect_conflict(start, end, existing, "America/Toronto") is True

    def test_new_contains_existing(self):
        new_start = datetime(2025, 7, 1, 9, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 12, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is True

    def test_existing_contains_new(self):
        new_start = datetime(2025, 7, 1, 10, 15, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 10, 45, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is True

    def test_partial_overlap_new_starts_during_existing(self):
        new_start = datetime(2025, 7, 1, 10, 30, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 11, 30, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is True


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    def test_new_ends_when_existing_starts(self):
        """new_end == existing_start should NOT conflict (back-to-back)."""
        new_start = datetime(2025, 7, 1, 9, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False

    def test_new_starts_when_existing_ends(self):
        """new_start == existing_end should NOT conflict (back-to-back)."""
        new_start = datetime(2025, 7, 1, 11, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 12, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False

    def test_one_minute_overlap(self):
        new_start = datetime(2025, 7, 1, 10, 59, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 11, 30, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 12, 0, tzinfo=TZ),
            )
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is True

    def test_zero_duration_appointment(self):
        """start == end should not conflict with an adjacent appointment."""
        new_start = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            )
        ]
        # new_end (10:00) is NOT < appt_end (11:00) AND new_start (10:00) is NOT > appt_start (10:00)
        # 10:00 < 11:00 is True but 10:00 > 10:00 is False, so no conflict
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False


# =============================================================================
# Multiple Appointments
# =============================================================================


class TestMultipleAppointments:
    def test_conflict_with_second_of_three(self):
        new_start = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 11, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 8, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 9, 0, tzinfo=TZ),
            ),
            _make_appt(
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            ),
            _make_appt(
                datetime(2025, 7, 1, 12, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 13, 0, tzinfo=TZ),
            ),
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is True

    def test_no_conflict_between_two_existing(self):
        new_start = datetime(2025, 7, 1, 9, 0, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 10, 0, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 8, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 8, 30, tzinfo=TZ),
            ),
            _make_appt(
                datetime(2025, 7, 1, 10, 30, tzinfo=TZ),
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
            ),
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is False

    def test_new_spans_across_two_existing(self):
        new_start = datetime(2025, 7, 1, 8, 30, tzinfo=TZ)
        new_end = datetime(2025, 7, 1, 12, 30, tzinfo=TZ)
        existing = [
            _make_appt(
                datetime(2025, 7, 1, 9, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 10, 0, tzinfo=TZ),
            ),
            _make_appt(
                datetime(2025, 7, 1, 11, 0, tzinfo=TZ),
                datetime(2025, 7, 1, 12, 0, tzinfo=TZ),
            ),
        ]
        assert detect_conflict(new_start, new_end, existing, "America/Toronto") is True
