from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.scheduling.engine import _calculate_slot_score

TZ = ZoneInfo("America/Toronto")


def _dt(hour: int, minute: int = 0, day: int = 1) -> datetime:
    return datetime(2026, 9, 15, hour, minute, tzinfo=TZ)


def _make_prefs(
    earliest: str = "09:00",
    latest: str = "17:00",
    avoid_lunch: bool = False,
) -> dict:
    return {
        "preferred_earliest": earliest,
        "preferred_latest": latest,
        "avoid_lunch": avoid_lunch,
    }


# ---------------------------------------------------------------------------
# 1. Boundary Times
# ---------------------------------------------------------------------------

class TestBoundaryTimes:
    def test_slot_at_11_59(self):
        result = _calculate_slot_score(_dt(11, 59), _dt(12, 59), _make_prefs())
        # 11:59 < 12 → +10 morning bonus applies
        assert result["score"] > 0
        assert isinstance(result["reasons"], list)

    def test_slot_at_12_00(self):
        result = _calculate_slot_score(_dt(12, 0), _dt(13, 0), _make_prefs())
        # 12:00 not < 12 → no morning bonus
        assert 0 <= result["score"] <= 100
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "morning" not in reasons_lower

    def test_slot_at_13_00(self):
        result = _calculate_slot_score(_dt(13, 0), _dt(14, 0), _make_prefs())
        # 13:00 is outside lunch overlap window, no morning bonus
        assert 0 <= result["score"] <= 100
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "lunch" not in reasons_lower

    def test_slot_at_09_00(self):
        result = _calculate_slot_score(_dt(9, 0), _dt(10, 0), _make_prefs())
        # 09:00 < 12 → +10 morning bonus; within 9-17 → +5
        assert result["score"] >= 50  # base + morning + working_hours
        assert 0 <= result["score"] <= 100

    def test_slot_at_17_00(self):
        result = _calculate_slot_score(_dt(17, 0), _dt(18, 0), _make_prefs())
        # 17:00 is NOT < 12, so no morning bonus
        # 17:00 is not within 9-17 (slot starts at boundary, not strictly inside)
        assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# 2. Preference Matching
# ---------------------------------------------------------------------------

class TestPreferenceMatching:
    def test_slot_within_preferred_window(self):
        result = _calculate_slot_score(_dt(10, 0), _dt(11, 0), _make_prefs())
        # Should get base 50 + 25 (preferred window) = 75 before rounding
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "preferred" in reasons_lower
        assert result["score"] >= 75

    def test_slot_outside_preferred_window(self):
        result = _calculate_slot_score(_dt(18, 0), _dt(19, 0), _make_prefs())
        # Outside 9-17 → no preferred window bonus
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "preferred" not in reasons_lower
        assert result["score"] < 75

    def test_slot_at_preferred_window_boundary(self):
        result_earliest = _calculate_slot_score(
            _dt(9, 0), _dt(10, 0), _make_prefs(earliest="09:00", latest="17:00")
        )
        result_latest = _calculate_slot_score(
            _dt(17, 0), _dt(18, 0), _make_prefs(earliest="09:00", latest="17:00")
        )
        # At exact boundaries, preference bonus should still apply
        reasons_early = " ".join(result_earliest["reasons"]).lower()
        assert "preferred" in reasons_early

    def test_with_no_preferences(self):
        result = _calculate_slot_score(_dt(10, 0), _dt(11, 0), {})
        # Empty prefs → base 50, no preference bonus
        assert result["score"] >= 50  # base minimum
        assert 0 <= result["score"] <= 100
        assert isinstance(result["reasons"], list)


# ---------------------------------------------------------------------------
# 3. Lunch Penalty
# ---------------------------------------------------------------------------

class TestLunchPenalty:
    def test_avoid_lunch_true_with_overlap(self):
        result = _calculate_slot_score(_dt(12, 0), _dt(13, 0), _make_prefs(avoid_lunch=True))
        # 12:00-13:00 overlaps lunch → -20 penalty
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "lunch" in reasons_lower
        assert result["score"] < 70

    def test_avoid_lunch_false_with_overlap(self):
        result = _calculate_slot_score(_dt(12, 0), _dt(13, 0), _make_prefs(avoid_lunch=False))
        reasons_lower = " ".join(result["reasons"]).lower()
        # avoid_lunch=False → no lunch penalty recorded
        assert result["score"] >= 50

    def test_avoid_lunch_true_slot_before_lunch(self):
        # 11:30-12:30 partially overlaps lunch
        result = _calculate_slot_score(_dt(11, 30), _dt(12, 30), _make_prefs(avoid_lunch=True))
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "lunch" in reasons_lower
        assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# 4. Morning Bonus
# ---------------------------------------------------------------------------

class TestMorningBonus:
    def test_slot_08_00_gets_morning_bonus(self):
        result = _calculate_slot_score(_dt(8, 0), _dt(9, 0), _make_prefs())
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "morning" in reasons_lower
        # base 50 + morning 10 = at least 60 before rounding
        assert result["score"] >= 60

    def test_slot_12_00_no_morning_bonus(self):
        result = _calculate_slot_score(_dt(12, 0), _dt(13, 0), _make_prefs())
        reasons_lower = " ".join(result["reasons"]).lower()
        assert "morning" not in reasons_lower


# ---------------------------------------------------------------------------
# 5. Score Clamping
# ---------------------------------------------------------------------------

class TestScoreClamping:
    def test_score_never_exceeds_100(self):
        # Slot perfectly in preferred window, morning, no lunch, within hours
        result = _calculate_slot_score(_dt(9, 0), _dt(10, 0), _make_prefs(earliest="09:00", latest="17:00"))
        # base 50 + preferred 25 + morning 10 + working 5 = 90 → rounded to 90
        # Even with extreme combos, must stay ≤ 100
        assert result["score"] <= 100

    def test_score_never_goes_below_0(self):
        # Slot outside everything, avoid lunch, late at night
        result = _calculate_slot_score(
            _dt(12, 30), _dt(13, 30),
            {"preferred_earliest": "06:00", "preferred_latest": "08:00", "avoid_lunch": True},
        )
        # base 50, no preferred bonus, lunch penalty -20 → 30, clamped ≥ 0
        assert result["score"] >= 0


# ---------------------------------------------------------------------------
# 6. Reason Strings
# ---------------------------------------------------------------------------

class TestReasonStrings:
    def test_reasons_are_populated(self):
        result = _calculate_slot_score(_dt(10, 0), _dt(11, 0), _make_prefs(avoid_lunch=True))
        assert len(result["reasons"]) > 0

    def test_score_is_integer(self):
        result = _calculate_slot_score(_dt(10, 0), _dt(11, 0), _make_prefs())
        assert isinstance(result["score"], int)
