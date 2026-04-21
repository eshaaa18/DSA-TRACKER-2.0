from fastapi import APIRouter, Request, Depends, Query
from database import Database
from auth import auth_middleware, get_user_id, is_admin
from loggings import get_logger
from security import Validate, rate_limiter, get_client_ip, RateLimiter
from response import *
from schemas import CreateProblemRequest, UpdateProblemRequest

router = APIRouter(tags=["Problems"])
logger = get_logger(__name__)


def get_db():
    return Database()


@router.get(
    "/",
    summary="List all problems (filterable by topic/difficulty/search)",
)
async def list_problems(
    request: Request,
    _=Depends(auth_middleware),
    topic: str = Query(default="", description="Filter by topic, e.g. 'Arrays & Hashing'"),
    difficulty: str = Query(default="", description="Easy / Medium / Hard"),
    search: str = Query(default="", description="Search title or description"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    db = get_db()
    ip = get_client_ip(request)
    if not rate_limiter.allow("api:" + ip, *RateLimiter.API()):
        return too_many_requests()

    if difficulty and difficulty not in ("Easy", "Medium", "Hard"):
        return bad_request("difficulty must be Easy, Medium, or Hard")

    offset = (page - 1) * limit
    safe_topic = Validate.safe_search(topic)
    safe_search = Validate.safe_search(search)
    query = (
        f"/rest/v1/problems?"
        f"select=problem_id,title,description,topic,difficulty,leetcode_slug,tags,created_at"
        f"&order=problem_id.asc&limit={limit}&offset={offset}"
    )
    if safe_topic:
        query += f"&topic=eq.{safe_topic}"
    if difficulty:
        query += f"&difficulty=eq.{difficulty}"
    if safe_search:
        query += f"&or=(title.ilike.*{safe_search}*,description.ilike.*{safe_search}*)"

    try:
        res = await db.GET(query, service=True)
        return list_response(res.json, -1, page, limit)
    except Exception:
        logger.error("list_problems_error", exc_info=True)
        return internal()


@router.get(
    "/{id}",
    summary="Get a single problem by ID",
)
async def get_problem(id: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    try:
        res = await db.GET(f"/rest/v1/problems?problem_id=eq.{id}&select=*", service=True)
        if not res.json:
            return not_found("Problem not found")
        return ok(res.json[0])
    except Exception:
        logger.error("get_problem_error", extra={"problem_id": id}, exc_info=True)
        return internal()


@router.post(
    "/admin",
    status_code=201,
    summary="[Admin] Create a new problem",
)
async def create_problem(
    body: CreateProblemRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    try:
        row = {
            "title": body.title,
            "topic": body.topic,
            "difficulty": body.difficulty,
            "description": body.description,
            "leetcode_slug": body.leetcode_slug,
            "created_by": get_user_id(request),
            "tags": body.tags,
        }
        res = await db.POST("/rest/v1/problems", [row], service=True)
        if not res.ok():
            return internal()
        return created(res.json[0])
    except Exception:
        logger.error("create_problem_error", exc_info=True)
        return internal()


@router.patch(
    "/admin/{id}",
    summary="[Admin] Update a problem",
)
async def update_problem(
    id: int,
    body: UpdateProblemRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    patch = body.model_dump(exclude_none=True)
    if not patch:
        return bad_request("Nothing to update")
    if "difficulty" in patch and patch["difficulty"] not in ("Easy", "Medium", "Hard"):
        return bad_request("difficulty must be Easy, Medium, or Hard")
    try:
        await db.PATCH(f"/rest/v1/problems?problem_id=eq.{id}", patch, service=True)
        return ok({"message": "Problem updated"})
    except Exception:
        logger.error("update_problem_error", extra={"problem_id": id}, exc_info=True)
        return internal()


@router.delete(
    "/admin/{id}",
    status_code=204,
    summary="[Admin] Delete a problem",
)
async def delete_problem(
    id: int,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    try:
        await db.DELETE(f"/rest/v1/problems?problem_id=eq.{id}", service=True)
        return no_content()
    except Exception:
        logger.error("delete_problem_error", extra={"problem_id": id}, exc_info=True)
        return internal()