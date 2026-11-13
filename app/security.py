import hmac
import time
from collections import defaultdict, deque

from fastapi import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

ADMIN_TOKEN_MAX_AGE = 30 * 24 * 3600


class FailureLimiter:
    def __init__(self, max_failures: int = 15, window_seconds: int = 600):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        entries = self._failures[key]
        cutoff = time.monotonic() - self.window_seconds
        while entries and entries[0] < cutoff:
            entries.popleft()
        return entries

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.max_failures

    def record_failure(self, key: str) -> None:
        self._prune(key).append(time.monotonic())


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AdminTokens:
    def __init__(self, secret_key: str, password: str):
        self._serializer = URLSafeTimedSerializer(secret_key, salt="admin")
        self._password = password

    @property
    def enabled(self) -> bool:
        return bool(self._password)

    def password_matches(self, candidate: str) -> bool:
        return self.enabled and hmac.compare_digest(candidate.encode(), self._password.encode())

    def issue(self) -> str:
        return self._serializer.dumps("admin")

    def valid(self, token: str) -> bool:
        try:
            return self._serializer.loads(token, max_age=ADMIN_TOKEN_MAX_AGE) == "admin"
        except BadSignature:
            return False
