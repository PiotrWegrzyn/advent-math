from decimal import Decimal

import pytest

from app.answers import is_correct, parse_answer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("12", Decimal("12")), ("3,5", Decimal("3.5")), ("3.5", Decimal("3.5")), (" -4 ", Decimal("-4")), ("1 200", Decimal("1200"))],
)
def test_parse_answer_accepts_numbers(raw, expected):
    result = parse_answer(raw)

    assert result == expected


@pytest.mark.parametrize("raw", ["", "abc", "3/4", "1,2,3", "--1", "5-"])
def test_parse_answer_rejects_non_numbers(raw):
    result = parse_answer(raw)

    assert result is None


def test_is_correct_ignores_trailing_zeros():
    given = parse_answer("2,50")

    result = is_correct(given, "2,5")

    assert result is True
