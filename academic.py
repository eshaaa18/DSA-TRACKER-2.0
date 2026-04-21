from fastapi import APIRouter, Request, Depends, Query
from database import Database
from auth import auth_middleware, get_user_id, get_role, is_admin
from loggings import get_logger
from security import Validate
from response import *
from schemas import UpsertAcademicRequest, SetRoleRequest

router = APIRouter(tags=["Academic & Admin"])
logger = get_logger(__name__)


def get_db():
    return Database()


@router.get(
    "/academic/{uid}",
    summary="Get my academic record (or any user's if admin)",
)
async def get_academic(uid: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    me = get_user_id(request)
    if get_role(request) != "admin" and me != uid:
        return forbidden()
    try:
        res = await db.GET(f"/rest/v1/academic_records?user_id=eq.{uid}&select=*", True)
        if not res.json:
            return ok({
                "user_id": uid,
                "cgpa": 0.0,
                "attendance_percentage": 0,
                "semester": "",
                "branch": "",
                "last_updated": "N/A",
            })
        return ok(res.json[0])
    except Exception:
        logger.error("get_academic_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.post(
    "/admin/academic",
    summary="[Admin] Upsert a student's academic record",
)
async def upsert_academic(
    body: UpsertAcademicRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    row = {
        "user_id": body.user_id,
        "cgpa": body.cgpa,
        "attendance_percentage": body.attendance,
        "semester": body.semester,
        "branch": body.branch,
    }
    try:
        await db.POST("/rest/v1/academic_records?on_conflict=user_id", [row], True)
        return ok({"message": "Academic record updated", "user_id": body.user_id})
    except Exception:
        logger.error("upsert_academic_error", extra={"user_id": body.user_id}, exc_info=True)
        return internal()


@router.get(
    "/admin/students",
    summary="[Admin] List all students (paginated, searchable)",
)
async def students(
    request: Request,
    _=Depends(auth_middleware),
    page: int = Query(default=1, ge=1, description="Page number"),
    search: str = Query(default="", description="Search by username or email"),
):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    limit = 20
    offset = (page - 1) * limit
    safe_search = Validate.safe_search(search)
    query = (
        f"/rest/v1/users?role=eq.student"
        f"&select=*,academic_records(*),streaks(*)"
        f"&order=created_at.desc"
        f"&limit={limit}&offset={offset}"
    )
    if safe_search:
        query += f"&or=(username.ilike.*{safe_search}*,email.ilike.*{safe_search}*)"
    try:
        res = await db.GET(query, True)
        return list_response(res.json, -1, page, limit)
    except Exception:
        logger.error("list_students_error", exc_info=True)
        return internal()


@router.get(
    "/admin/students/{uid}",
    summary="[Admin] Get full student profile with stats",
)
async def get_student(uid: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    try:
        profile = await db.GET(
            f"/rest/v1/users?user_id=eq.{uid}&select=*,academic_records(*),streaks(*)",
            True,
        )
        if not profile.json:
            return not_found("Student not found")
        stats = await db.RPC("get_user_stats", {"p_user_id": uid})
        weak = await db.RPC("get_weak_topics", {"p_user_id": uid})
        return ok({
            "profile": profile.json[0],
            "stats": stats.json,
            "weak_topics": weak.json,
        })
    except Exception:
        logger.error("get_student_error", extra={"user_id": uid}, exc_info=True)
        return internal()


@router.get(
    "/admin/overview",
    summary="[Admin] Get platform-wide overview stats",
)
async def overview(request: Request, _=Depends(auth_middleware)):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    try:
        res = await db.RPC("get_admin_overview", {})
        return ok(res.json)
    except Exception:
        logger.error("admin_overview_error", exc_info=True)
        return internal()


@router.patch(
    "/admin/users/{uid}/role",
    summary="[Admin] Change a user's role",
)
async def set_role(
    uid: int,
    body: SetRoleRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    if not is_admin(request):
        return forbidden("Admin only")
    try:
        await db.PATCH(
            f"/rest/v1/users?user_id=eq.{uid}",
            {"role": body.role},
            True,
        )
        return ok({"message": "Role updated", "user_id": uid, "role": body.role})
    except Exception:
        logger.error("set_role_error", extra={"user_id": uid}, exc_info=True)
        return internal()