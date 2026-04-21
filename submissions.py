from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Query
from auth import auth_middleware, get_role, get_user_id, is_admin
from database import Database
from loggings import get_logger
from schemas import LCSyncRequest, SubmitRequest
from security import RateLimiter, get_client_ip, rate_limiter
from response import (
    created, forbidden, internal, list_response,
    not_found, ok, too_many_requests,
)

router = APIRouter(tags=["Submissions"])
logger = get_logger(__name__)


def get_db():
    return Database()


@router.post(
    "/submit",
    status_code=201,
    summary="Submit a solution to an internal problem",
    description="Records your solution attempt. Use status 'Accepted' to update your streak.",
)
async def submit(
    body: SubmitRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    ip = get_client_ip(request)
    if not rate_limiter.allow("sub:" + ip, *RateLimiter.SUBMIT()):
        return too_many_requests()

    uid = get_user_id(request)
    try:
        check = await db.GET(
            f"/rest/v1/problems?problem_id=eq.{body.problem_id}&select=problem_id",
            service=True,
        )
        if not check.json:
            return not_found("Problem not found")

        res = await db.POST(
            "/rest/v1/submissions",
            [{
                "user_id": uid,
                "problem_id": body.problem_id,
                "status": body.status,
                "language": body.language,
                "time_ms": body.time_ms,
                "memory_kb": body.memory_kb,
                "notes": body.notes,
            }],
            service=True,
        )
        if not res.ok():
            logger.error("submit_db_fail", extra={"user_id": uid})
            return internal()

        streak_data = {}
        if body.status == "Accepted":
            await db.RPC("update_streak", {"p_user_id": uid})
            streak_res = await db.GET(
                f"/rest/v1/streaks?user_id=eq.{uid}&select=current_streak,longest_streak",
                service=True,
            )
            streak_data = streak_res.json[0] if streak_res.json else {}

        return created({
            "submission": res.json[0],
            "streak": streak_data,
            "message": "Accepted!" if body.status == "Accepted" else "Submission recorded",
        })
    except Exception:
        logger.error("submit_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.get(
    "/performance/{uid}",
    summary="Get submission history for a user",
)
async def history(
    uid: int,
    request: Request,
    _=Depends(auth_middleware),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str = Query(default="", alias="status", description="Filter by status e.g. Accepted"),
):
    db = get_db()
    me = get_user_id(request)
    if not is_admin(request) and me != uid:
        return forbidden()

    offset = (page - 1) * limit
    query = (
        f"/rest/v1/submissions?user_id=eq.{uid}"
        f"&select=*,problems(*)"
        f"&order=submitted_at.desc"
        f"&limit={limit}&offset={offset}"
    )
    if status_filter:
        query += f"&status=eq.{status_filter}"
    try:
        res = await db.GET(query, service=True)
        return list_response(res.json, page=page, limit=limit)
    except Exception:
        logger.error("performance_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.get(
    "/performance/{uid}/stats",
    summary="Get aggregated stats for a user (total solved, by difficulty, etc.)",
)
async def stats(uid: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    me = get_user_id(request)
    if not is_admin(request) and me != uid:
        return forbidden()
    try:
        res = await db.RPC("get_user_stats", {"p_user_id": uid})
        return ok(res.json)
    except Exception:
        logger.error("stats_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.get(
    "/performance/{uid}/heatmap",
    summary="Get submission heatmap (daily activity for the past year)",
)
async def heatmap(uid: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    me = get_user_id(request)
    if not is_admin(request) and me != uid:
        return forbidden()
    try:
        res = await db.RPC("get_submission_heatmap", {"p_user_id": uid})
        return ok(res.json)
    except Exception:
        logger.error("heatmap_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.post(
    "/leetcode/sync",
    summary="Bulk sync LeetCode solved problems",
    description="Send a list of solved LeetCode slugs. Uses upsert — safe to call multiple times.",
)
async def lc_sync(
    body: LCSyncRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    uid = get_user_id(request)
    try:
        rows = [
            {
                "user_id": uid,
                "lc_slug": item.slug,
                "title": item.title or item.slug,
                "difficulty": item.difficulty,
                "status": "Accepted",
            }
            for item in body.solved
        ]
        if not rows:
            return ok({"synced": 0, "message": "Nothing to sync"})

        res = await db.POST(
            "/rest/v1/leetcode_submissions?on_conflict=user_id,lc_slug",
            rows,
            service=True,
        )
        count = len(rows) if res.ok() else 0
        return ok({"synced": count, "message": f"Synced {count} problems"})
    except Exception:
        logger.error("lc_sync_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.get(
    "/leetcode/{uid}",
    summary="Get all synced LeetCode submissions for a user",
)
async def lc_history(uid: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    me = get_user_id(request)
    if not is_admin(request) and me != uid:
        return forbidden()
    try:
        res = await db.GET(
            f"/rest/v1/leetcode_submissions?user_id=eq.{uid}&select=*",
            service=True,
        )
        return ok(res.json)
    except Exception:
        logger.error("lc_history_error", extra={"user_id": uid}, exc_info=True)
        return internal()