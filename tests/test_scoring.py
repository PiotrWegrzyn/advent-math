import pytest

from app.scoring import base_points, breakdown, day_points, streak_before


@pytest.mark.parametrize(
    ("elapsed", "wrong", "expected"),
    [
        (0, 0, 100),
        (300, 0, 100),
        (301, 0, 90),
        (360, 0, 90),
        (361, 0, 80),
        (300, 3, 97),
        (420, 3, 77),
        (3600, 0, 10),
        (0, 500, 10),
    ],
)
def test_base_points(elapsed, wrong, expected):
    result = base_points(elapsed, wrong)

    assert result == expected


@pytest.mark.parametrize(
    ("elapsed", "wrong", "streak", "expected"),
    [
        (0, 0, 0, 100),
        (0, 0, 1, 110),
        (420, 3, 4, 113),
        (0, 0, 23, 895),
        (3600, 0, 0, 10),
    ],
)
def test_day_points(elapsed, wrong, streak, expected):
    result = day_points(elapsed, wrong, streak)

    assert result == expected


@pytest.mark.parametrize(
    ("solved", "day", "expected"),
    [
        (set(), 1, 0),
        ({1, 2, 3}, 4, 3),
        ({1, 3}, 4, 1),
        ({1, 2}, 4, 0),
    ],
)
def test_streak_before(solved, day, expected):
    result = streak_before(solved, day)

    assert result == expected


def test_breakdown_explains_points():
    result = breakdown(420, 3, 4)

    assert result == {
        "elapsed_seconds": 420,
        "started_minutes_over": 2,
        "time_penalty": 20,
        "wrong_attempts": 3,
        "wrong_penalty": 3,
        "raw": 77,
        "base": 77,
        "minimum_applied": False,
        "streak": 4,
        "multiplier": 1.4641,
        "points": 113,
    }


def test_breakdown_marks_minimum_points():
    result = breakdown(3600, 0, 0)

    assert result["raw"] == -450
    assert result["base"] == 10
    assert result["minimum_applied"] is True
