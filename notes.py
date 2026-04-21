from fastapi import APIRouter, Request, Depends, Query
from database import Database
from auth import auth_middleware, get_user_id
from loggings import get_logger
from security import Validate
from response import *
from schemas import CreateNoteRequest, UpdateNoteRequest

router = APIRouter(tags=["Notes"])
logger = get_logger(__name__)


def get_db():
    return Database()


@router.get(
    "/notes",
    summary="List my notes (filterable by topic/problem)",
)
async def list_notes(
    request: Request,
    _=Depends(auth_middleware),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    problem_id: int = Query(default=None, description="Filter by problem ID"),
    topic: str = Query(default="", description="Filter by topic"),
):
    db = get_db()
    uid = get_user_id(request)
    offset = (page - 1) * limit
    query = (
        f"/rest/v1/notes?user_id=eq.{uid}"
        f"&select=*,problems(*)"
        f"&order=pinned.desc,updated_at.desc"
        f"&limit={limit}&offset={offset}"
    )
    if problem_id is not None:
        query += f"&problem_id=eq.{problem_id}"
    if topic:
        query += f"&topic=eq.{Validate.safe_search(topic)}"
    try:
        res = await db.GET(query, True)
        return list_response(res.json, -1, page, limit)
    except Exception:
        return internal()


@router.get(
    "/notes/search",
    summary="Full-text search across note titles and content",
)
async def search_notes(
    request: Request,
    _=Depends(auth_middleware),
    q: str = Query(..., min_length=1, description="Search term"),
    page: int = Query(default=1, ge=1),
):
    db = get_db()
    uid = get_user_id(request)
    safe_q = Validate.safe_search(q)
    limit = 20
    offset = (page - 1) * limit
    try:
        res = await db.GET(
            f"/rest/v1/notes?user_id=eq.{uid}"
            f"&or=(title.ilike.*{safe_q}*,content.ilike.*{safe_q}*)"
            f"&order=updated_at.desc&limit={limit}&offset={offset}",
            True,
        )
        return list_response(res.json, -1, page, limit)
    except Exception:
        return internal()


@router.get(
    "/notes/{id}",
    summary="Get a single note by ID",
)
async def get_note(id: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    uid = get_user_id(request)
    try:
        res = await db.GET(
            f"/rest/v1/notes?note_id=eq.{id}&user_id=eq.{uid}&select=*",
            True,
        )
        if not res.json:
            return not_found("Note not found")
        return ok(res.json[0])
    except Exception:
        return internal()


@router.post(
    "/notes",
    status_code=201,
    summary="Create a new note",
)
async def create_note(
    body: CreateNoteRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    uid = get_user_id(request)
    row = {
        "user_id": uid,
        "title": Validate.sanitize(body.title, 200),
        "content": body.content,
        "topic": body.topic,
        "pinned": body.pinned,
        "problem_id": body.problem_id,
        "tags": body.tags,
    }
    try:
        res = await db.POST("/rest/v1/notes", [row], True)
        if not res.ok():
            return internal()
        return created(res.json[0])
    except Exception:
        return internal()


@router.patch(
    "/notes/{id}",
    summary="Update a note",
)
async def update_note(
    id: int,
    body: UpdateNoteRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    uid = get_user_id(request)
    patch = {}
    if body.title is not None:
        patch["title"] = Validate.sanitize(body.title, 200)
    if body.content is not None:
        patch["content"] = body.content
    if body.topic is not None:
        patch["topic"] = body.topic
    if body.pinned is not None:
        patch["pinned"] = body.pinned
    if body.tags is not None:
        patch["tags"] = body.tags
    if not patch:
        return bad_request("Nothing to update")
    try:
        await db.PATCH(
            f"/rest/v1/notes?note_id=eq.{id}&user_id=eq.{uid}",
            patch,
            True,
        )
        return ok({"message": "Note updated", "note_id": id})
    except Exception:
        return internal()


@router.delete(
    "/notes/{id}",
    status_code=204,
    summary="Delete a note",
)
async def delete_note(id: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    uid = get_user_id(request)
    try:
        await db.DELETE(
            f"/rest/v1/notes?note_id=eq.{id}&user_id=eq.{uid}",
            True,
        )
        return no_content()
    except Exception:
        return internal()


@router.post(
    "/notes/{id}/pin",
    summary="Toggle pin/unpin a note",
)
async def toggle_pin(id: int, request: Request, _=Depends(auth_middleware)):
    db = get_db()
    uid = get_user_id(request)
    try:
        res = await db.GET(
            f"/rest/v1/notes?note_id=eq.{id}&user_id=eq.{uid}&select=pinned",
            True,
        )
        if not res.json:
            return not_found("Note not found")
        current = res.json[0]["pinned"]
        await db.PATCH(
            f"/rest/v1/notes?note_id=eq.{id}&user_id=eq.{uid}",
            {"pinned": not current},
            True,
        )
        return ok({"note_id": id, "pinned": not current})
    except Exception:
        return internal()