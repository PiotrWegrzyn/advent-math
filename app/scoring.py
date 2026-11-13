import math

BASE_POINTS = 100
FREE_SECONDS = 5 * 60
MINUTE_PENALTY = 10
WRONG_ANSWER_PENALTY = 1
MIN_POINTS = 10
STREAK_BONUS = 1.1


def base_points(elapsed_seconds: int, wrong_attempts: int) -> int:
    started_minutes_over = math.ceil(max(0, elapsed_seconds - FREE_SECONDS) / 60)
    raw = BASE_POINTS - MINUTE_PENALTY * started_minutes_over - WRONG_ANSWER_PENALTY * wrong_attempts
    return max(MIN_POINTS, raw)


def multiplier(streak: int) -> float:
    return STREAK_BONUS**streak


def day_points(elapsed_seconds: int, wrong_attempts: int, streak: int) -> int:
    return math.floor(base_points(elapsed_seconds, wrong_attempts) * multiplier(streak) + 0.5)


def streak_before(solved_days: set[int], day: int) -> int:
    streak = 0
    previous = day - 1
    while previous in solved_days:
        streak += 1
        previous -= 1
    return streak


def breakdown(elapsed_seconds: int, wrong_attempts: int, streak: int) -> dict[str, int | float | bool]:
    started_minutes_over = math.ceil(max(0, elapsed_seconds - FREE_SECONDS) / 60)
    raw = BASE_POINTS - MINUTE_PENALTY * started_minutes_over - WRONG_ANSWER_PENALTY * wrong_attempts
    base = max(MIN_POINTS, raw)
    return {
        "elapsed_seconds": elapsed_seconds,
        "started_minutes_over": started_minutes_over,
        "time_penalty": MINUTE_PENALTY * started_minutes_over,
        "wrong_attempts": wrong_attempts,
        "wrong_penalty": WRONG_ANSWER_PENALTY * wrong_attempts,
        "raw": raw,
        "base": base,
        "minimum_applied": raw < MIN_POINTS,
        "streak": streak,
        "multiplier": round(multiplier(streak), 4),
        "points": day_points(elapsed_seconds, wrong_attempts, streak),
    }
