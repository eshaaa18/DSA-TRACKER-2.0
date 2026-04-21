from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


def ok(data: Any) -> JSONResponse:
    return JSONResponse({"success": True, "data": data}, status_code=status.HTTP_200_OK)


def created(data: Any) -> JSONResponse:
    return JSONResponse({"success": True, "data": data}, status_code=status.HTTP_201_CREATED)


def no_content() -> JSONResponse:
    return JSONResponse(None, status_code=status.HTTP_204_NO_CONTENT)


def _error(code: int, message: str, err_code: str | None = None) -> JSONResponse:
    body: dict[str, Any] = {"success": False, "error": message}
    if err_code:
        body["code"] = err_code
    return JSONResponse(body, status_code=code)


def bad_request(msg: str) -> JSONResponse:
    return _error(status.HTTP_400_BAD_REQUEST, msg, "BAD_REQUEST")


def unauthorized(msg: str = "Unauthorized") -> JSONResponse:
    return _error(status.HTTP_401_UNAUTHORIZED, msg, "UNAUTHORIZED")


def forbidden(msg: str = "Access denied") -> JSONResponse:
    return _error(status.HTTP_403_FORBIDDEN, msg, "FORBIDDEN")


def not_found(msg: str = "Not found") -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, msg, "NOT_FOUND")


def conflict(msg: str) -> JSONResponse:
    return _error(status.HTTP_409_CONFLICT, msg, "CONFLICT")


def too_many_requests() -> JSONResponse:
    return _error(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many requests. Please slow down.",
        "RATE_LIMITED",
    )


def internal(msg: str = "An unexpected error occurred") -> JSONResponse:
    return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, msg, "INTERNAL_ERROR")


def list_response(
    items: list[Any],
    total: int = -1,
    page: int = 1,
    limit: int = 20,
) -> JSONResponse:
    body: dict[str, Any] = {"success": True, "data": items}
    if total >= 0:
        body["pagination"] = {
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": (page * limit) < total,
        }
    return JSONResponse(body, status_code=status.HTTP_200_OK)