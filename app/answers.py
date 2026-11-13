import re
from decimal import Decimal

ANSWER_PATTERN = re.compile(r"^-?\d+([.,]\d+)?$")


def parse_answer(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace(" ", "")
    if not ANSWER_PATTERN.match(cleaned):
        return None
    return Decimal(cleaned.replace(",", "."))


def is_correct(given: Decimal, expected: str) -> bool:
    return given == parse_answer(expected)
