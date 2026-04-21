from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Request

from loggings import get_logger

logger = get_logger(__name__)


# ================= TOKEN PAYLOAD =================
@dataclass(frozen=True, slots=True)
class TokenPayload:
    user_id: int
    username: str
    email: str
    role: str
    jti: str


# ================= TOKEN BLACKLIST =================
class _TokenBlacklist:
    def __init__(self) -> None:
        self._store: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def revoke(self, jti: str, expires_at: datetime) -> None:
        with self._lock:
            self._store[jti] = expires_at

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            self._purge()
            return jti in self._store

    def _purge(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self._store.items() if v < now]
        for k in expired:
            del self._store[k]


blacklist = _TokenBlacklist()


# ================= JWT HANDLER =================
class JWTHandler:
    TTL_HOURS = 24

    @staticmethod
    def _secret() -> str:
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise RuntimeError("JWT_SECRET env var not set")
        return secret

    @classmethod
    def generate(cls, user_id: int, username: str, email: str, role: str) -> tuple[str, str]:
        import secrets as _secrets
        jti = _secrets.token_hex(16)
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=cls.TTL_HOURS)
        payload = {
            "iss": "dsa-tracker",
            "sub": str(user_id),
            "jti": jti,
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "iat": now,
            "exp": exp,
        }
        token = jwt.encode(payload, cls._secret(), algorithm="HS256")
        return token, jti

    @classmethod
    def verify(cls, token: str) -> Optional[TokenPayload]:
        try:
            decoded = jwt.decode(
                token,
                cls._secret(),
                algorithms=["HS256"],
                issuer="dsa-tracker",
            )
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_expired")
            return None
        except jwt.InvalidTokenError as exc:
            logger.warning("jwt_invalid", extra={"reason": str(exc)})
            return None

        jti = decoded.get("jti", "")
        if blacklist.is_revoked(jti):
            logger.warning("jwt_blacklisted", extra={"jti": jti})
            return None

        return TokenPayload(
            user_id=int(decoded["user_id"]),
            username=decoded["username"],
            email=decoded["email"],
            role=decoded["role"],
            jti=jti,
        )


# ================= HELPER =================
def _extract_bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ")
    return None


# ================= MIDDLEWARE =================
async def auth_middleware(request: Request) -> None:
    # Allow Swagger / OpenAPI docs without auth
    skip_paths = ("/docs", "/openapi.json", "/redoc")
    if any(request.url.path.startswith(p) for p in skip_paths):
        return

    # Allow preflight
    if request.method == "OPTIONS":
        return

    token = _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing Authorization header", "code": "UNAUTHORIZED"},
        )

    payload = JWTHandler.verify(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid or expired token", "code": "TOKEN_EXPIRED"},
        )

    request.state.user_id = payload.user_id
    request.state.username = payload.username
    request.state.email = payload.email
    request.state.role = payload.role
    request.state.jti = payload.jti


# ================= GETTERS =================
def get_user_id(request: Request) -> int:
    return request.state.user_id


def get_role(request: Request) -> str:
    return request.state.role


def get_jti(request: Request) -> str:
    return request.state.jti


def is_admin(request: Request) -> bool:
    return get_role(request) == "admin"