from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request


class RateLimiter:
    def __init__(self) -> None:
        self._store: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_requests: int, window_secs: int) -> bool:
        now = time.monotonic()
        dq = self._store[key]
        cutoff = now - window_secs
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_requests:
            return False
        dq.append(now)
        return True

    LOGIN = staticmethod(lambda: (5, 60))
    REGISTER = staticmethod(lambda: (3, 60))
    API = staticmethod(lambda: (120, 60))
    SUBMIT = staticmethod(lambda: (30, 60))


rate_limiter = RateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class Password:
    ITERATIONS = 260_000

    @staticmethod
    def _pbkdf2(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            Password.ITERATIONS,
        ).hex()

    @classmethod
    def hash(cls, password: str) -> str:
        salt = secrets.token_hex(16)
        hashed = cls._pbkdf2(password, salt)
        return f"{salt}${hashed}"

    @classmethod
    def verify(cls, password: str, stored: str) -> bool:
        if "$" not in stored:
            return False
        salt, expected = stored.split("$", 1)
        actual = cls._pbkdf2(password, salt)
        return hmac.compare_digest(actual, expected)


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,30}$")
_DANGEROUS = re.compile(r"[<>\"\'\\\x00]")


class Validate:
    @staticmethod
    def email(e: str) -> bool:
        return bool(_EMAIL_RE.match(e))

    @staticmethod
    def username(u: str) -> bool:
        return bool(_USERNAME_RE.match(u))

    @staticmethod
    def password(p: str) -> bool:
        return (
            len(p) >= 8
            and any(c.isupper() for c in p)
            and any(c.islower() for c in p)
            and any(c.isdigit() for c in p)
        )

    @staticmethod
    def sanitize(s: str, max_len: int = 500) -> str:
        return _DANGEROUS.sub("", s[:max_len])

    @staticmethod
    def safe_search(s: str, max_len: int = 100) -> str:
        cleaned = _DANGEROUS.sub("", s[:max_len])
        return re.sub(r"[%*&|(){}]", "", cleaned)