from datetime import date, timedelta
from typing import List

import pytest

from app.scheduling.engine import expand_recurrence


class TestDailyRecurrence:
    def test_daily_five_days(self):
        result = expand_recurrence("daily", date(2026, 9, 1), 30, date(2026, 9, 5))
        assert len(result) == 5
        assert result == [
            date(2026, 9, 1),
            date(2026, 9, 2),
            date(2026, 9, 3),
            date(2026, 9, 4),
            date(2026, 9, 5),
        ]

    def test_daily_interval_2(self):
        result = expand_recurrence("daily", date(2026, 9, 1), 30, date(2026, 9, 10), interval=2)
        assert result == [
            date(2026, 9, 1),
            date(2026, 9, 3),
            date(2026, 9, 5),
            date(2026, 9, 7),
            date(2026, 9, 9),
        ]

    def test_daily_sep_1_to_sep_10(self):
        result = expand_recurrence("daily", date(2026, 9, 1), 30, date(2026, 9, 10))
        assert len(result) == 10
        assert result[0] == date(2026, 9, 1)
        assert result[-1] == date(2026, 9, 10)


class TestWeeklyRecurrence:
    def test_weekly_four_weeks(self):
        result = expand_recurrence("weekly", date(2026, 9, 1), 60, date(2026, 9, 28))
        assert len(result) == 4
        assert result == [
            date(2026, 9, 1),
            date(2026, 9, 8),
            date(2026, 9, 15),
            date(2026, 9, 22),
        ]

    def test_weekly_interval_2(self):
        result = expand_recurrence("weekly", date(2026, 9, 1), 60, date(2026, 9, 28), interval=2)
        assert result == [
            date(2026, 9, 1),
            date(2026, 9, 15),
        ]

    def test_weekly_starting_friday(self):
        result = expand_recurrence("weekly", date(2026, 9, 4), 60, date(2026, 9, 25))
        assert result == [
            date(2026, 9, 4),
            date(2026, 9, 11),
            date(2026, 9, 18),
            date(2026, 9, 25),
        ]


class TestMonthlyRecurrence:
    def test_monthly_three_months(self):
        result = expand_recurrence("monthly", date(2026, 9, 15), 60, date(2026, 11, 15))
        assert len(result) == 3
        assert result == [
            date(2026, 9, 15),
            date(2026, 10, 15),
            date(2026, 11, 15),
        ]

    def test_monthly_interval_2(self):
        result = expand_recurrence("monthly", date(2026, 1, 10), 30, date(2026, 7, 10), interval=2)
        assert result == [
            date(2026, 1, 10),
            date(2026, 3, 10),
            date(2026, 5, 10),
            date(2026, 7, 10),
        ]

    def test_monthly_jan_31_handles_month_end(self):
        result = expand_recurrence("monthly", date(2026, 1, 31), 30, date(2026, 6, 30))
        assert result[0] == date(2026, 1, 31)
        assert result[1] == date(2026, 2, 28)
        assert result[2] == date(2026, 3, 28)
        assert result[3] == date(2026, 4, 28)
        assert result[4] == date(2026, 5, 28)
        assert result[5] == date(2026, 6, 28)

    def test_monthly_spanning_year_boundary(self):
        result = expand_recurrence("monthly", date(2026, 11, 15), 60, date(2027, 1, 15))
        assert result == [
            date(2026, 11, 15),
            date(2026, 12, 15),
            date(2027, 1, 15),
        ]


class TestEdgeCases:
    def test_range_end_before_start_returns_empty(self):
        result = expand_recurrence("daily", date(2026, 9, 10), 30, date(2026, 9, 1))
        assert result == []

    def test_range_end_same_as_start_returns_one(self):
        result = expand_recurrence("daily", date(2026, 9, 5), 30, date(2026, 9, 5))
        assert result == [date(2026, 9, 5)]

    def test_very_short_range_one_day(self):
        result = expand_recurrence("daily", date(2026, 9, 1), 15, date(2026, 9, 1))
        assert result == [date(2026, 9, 1)]

    def test_very_long_range_365_days(self):
        start = date(2026, 1, 1)
        end = date(2026, 12, 31)
        result = expand_recurrence("daily", start, 30, end)
        assert len(result) == 365
        assert result[0] == date(2026, 1, 1)
        assert result[-1] == date(2026, 12, 31)

    def test_interval_1_matches_default(self):
        with_default = expand_recurrence("daily", date(2026, 9, 1), 30, date(2026, 9, 5))
        with_explicit = expand_recurrence("daily", date(2026, 9, 1), 30, date(2026, 9, 5), interval=1)
        assert with_default == with_explicit
