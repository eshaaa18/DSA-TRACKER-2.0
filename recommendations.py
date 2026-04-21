from fastapi import APIRouter, Request, Depends, Query
from database import Database
from auth import auth_middleware, get_user_id, get_role
from loggings import get_logger
from response import *
from leetcode_bank import get_recommendations

router = APIRouter(tags=["Recommendations"])
logger = get_logger(__name__)


def get_db():
    return Database()


@router.get(
    "/weakness/{uid}",
    summary="Get weak topics for a user (based on failure rate)",
)
async def weakness(uid: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    me = get_user_id(request)
    if get_role(request) != "admin" and me != uid:
        return forbidden()
    try:
        res = await db.RPC("get_weak_topics", {"p_user_id": uid})
        enriched = []
        for topic_row in res.json:
            rate = topic_row["failure_rate"]
            if rate > 70:
                topic_row["suggested_difficulty"] = "Easy"
            elif rate > 40:
                topic_row["suggested_difficulty"] = "Medium"
            else:
                topic_row["suggested_difficulty"] = "Hard"
            enriched.append(topic_row)
        return ok({
            "weak_topics": enriched,
            "total_topics_weak": len(enriched),
            "user_id": uid,
        })
    except Exception:
        logger.error("weakness_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.get(
    "/recommendations/{uid}",
    summary="Get personalised LeetCode recommendations based on weak topics",
)
async def recommendations(
    uid: int,
    request: Request,
    _=Depends(auth_middleware),
    limit: int = Query(default=15, ge=1, le=50, description="Max number of recommendations"),
    topic: str = Query(default="", description="Filter by topic"),
    difficulty: str = Query(default="", description="Filter by difficulty"),
):
    db = get_db()
    me = get_user_id(request)
    if get_role(request) != "admin" and me != uid:
        return forbidden()
    try:
        weak_res = await db.RPC("get_weak_topics", {"p_user_id": uid})
        weak_topics = [t["topic"] for t in weak_res.json]

        solved_res = await db.GET(
            f"/rest/v1/leetcode_submissions?user_id=eq.{uid}&status=eq.Accepted&select=lc_slug",
            True,
        )
        solved = {row["lc_slug"] for row in solved_res.json}

        bank_res = await db.GET(
            f"/rest/v1/submissions?user_id=eq.{uid}&status=eq.Accepted&select=problems(leetcode_slug)",
            True,
        )
        for row in bank_res.json:
            if row.get("problems") and row["problems"].get("leetcode_slug"):
                solved.add(row["problems"]["leetcode_slug"])

        recs = get_recommendations(weak_topics, solved, limit)
        if topic or difficulty:
            recs = [
                r for r in recs
                if (not topic or r["topic"] == topic)
                and (not difficulty or r["difficulty"] == difficulty)
            ]

        return ok({
            "recommendations": recs,
            "weak_topics": weak_res.json,
            "solved_count": len(solved),
            "user_id": uid,
        })
    except Exception:
        logger.error("recommendations_error", extra={"user_id": uid}, exc_info=True)
        return internal()