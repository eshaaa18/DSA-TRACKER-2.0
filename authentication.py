from fastapi import APIRouter, Depends, Request, HTTPException, Body
from database import Database
from loggings import get_logger
from schemas import (
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
    UpdateProfileRequest,
    RegisterResponse,
    LoginResponse,
)
from security import Password, RateLimiter, get_client_ip, rate_limiter
from auth import JWTHandler, auth_middleware, get_user_id, get_jti, blacklist
from datetime import datetime, timedelta, timezone

router = APIRouter(tags=["Auth"])
logger = get_logger(__name__)


def get_db():
    return Database()


# ================= REGISTER =================
from urllib.parse import quote

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest = Body(...),
    request: Request = None,
):
    db = get_db()

    # Rate limit
    ip = get_client_ip(request)
    if not rate_limiter.allow("reg:" + ip, *RateLimiter.REGISTER()):
        raise HTTPException(status_code=429, detail="Too many requests")

    # ✅ SAFE QUERY (IMPORTANT FIX)
    username = quote(body.username)
    email = quote(body.email)

    check = await db.GET(
        f"/rest/v1/users?or=(username.eq.{username},email.eq.{email})&select=user_id",
        service=True,
    )

    if check.json:
        raise HTTPException(status_code=409, detail="Username or email already taken")

    # Hash password
    pw_hash = Password.hash(body.password)

    # ✅ SAFE INSERT (remove risky fields temporarily)
    row = {
        "username": body.username,
        "email": body.email,
        "password_hash": pw_hash,
        "role": body.role or "student",   # safe default
    }

    res = await db.POST("/rest/v1/users", [row], service=True)

    # ✅ DEBUG + REAL ERROR RETURN
    if not res.ok():
        print("REGISTER ERROR:", res.status, res.body)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {res.body}"
        )

    user = res.json[0]
    uid = user["user_id"]

    # Create streak row
    await db.POST(
        "/rest/v1/streaks",
        [{"user_id": uid, "current_streak": 0, "longest_streak": 0}],
        service=True,
    )

    # Generate token
    token, _ = JWTHandler.generate(
        uid, body.username, body.email, row["role"]
    )

    return {
        "success": True,
        "data": {
            "token": token,
            "user": {
                "user_id": uid,
                "username": body.username,
                "email": body.email,
                "role": row["role"],
            },
        },
    }
# ================= LOGIN =================
@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description="Authenticate with email & password. Returns JWT token to use in the 🔒 Authorize button.",
)
async def login(
    body: LoginRequest = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Login example",
                "value": {"email": "alice@example.com", "password": "Secure123"},
            }
        },
    ),
    request: Request = None,
):
    db = get_db()
    ip = get_client_ip(request)
    if not rate_limiter.allow("login:" + ip, *RateLimiter.LOGIN()):
        raise HTTPException(status_code=429, detail="Too many requests")

    res = await db.GET(
        f"/rest/v1/users?email=eq.{body.email}&select=user_id,username,email,role,password_hash",
        service=True,
    )
    if not res.json:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = res.json[0]
    if not Password.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await db.PATCH(
        f"/rest/v1/users?user_id=eq.{user['user_id']}",
        {"last_seen": "now()"},
        service=True,
    )

    token, _ = JWTHandler.generate(
        user["user_id"], user["username"], user["email"], user["role"]
    )
    user.pop("password_hash", None)
    return {"success": True, "data": {"token": token, "user": user}}


# ================= LOGOUT =================
@router.post(
    "/logout",
    summary="Logout (invalidates token)",
)
async def logout(request: Request, _=Depends(auth_middleware)):
    jti = get_jti(request)
    exp = datetime.now(timezone.utc) + timedelta(hours=24)
    blacklist.revoke(jti, exp)
    return {"success": True, "data": {"message": "Logged out successfully"}}


# ================= ME =================
@router.get(
    "/me",
    summary="Get current user info",
)
async def me(request: Request, _=Depends(auth_middleware)):
    db = get_db()
    uid = get_user_id(request)
    res = await db.GET(
        f"/rest/v1/users?user_id=eq.{uid}&select=user_id,username,email,role",
        service=True,
    )
    if not res.json:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "data": res.json[0]}


# ================= CHANGE PASSWORD =================
@router.patch(
    "/password",
    summary="Change password",
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    uid = get_user_id(request)
    res = await db.GET(
        f"/rest/v1/users?user_id=eq.{uid}&select=password_hash",
        service=True,
    )
    if not res.json:
        raise HTTPException(status_code=404)
    if not Password.verify(body.old_password, res.json[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong password")

    new_hash = Password.hash(body.new_password)
    await db.PATCH(
        f"/rest/v1/users?user_id=eq.{uid}",
        {"password_hash": new_hash},
        service=True,
    )
    return {"success": True, "data": {"message": "Password updated"}}


# ================= UPDATE PROFILE =================
@router.patch(
    "/profile",
    summary="Update profile fields (bio, github, linkedin, leetcode username)",
)
async def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    _=Depends(auth_middleware),
):
    db = get_db()
    uid = get_user_id(request)
    patch = body.model_dump(exclude_none=True)
    if not patch:
        from response import bad_request
        return bad_request("Nothing to update")
    await db.PATCH(f"/rest/v1/users?user_id=eq.{uid}", patch, service=True)
    return {"success": True, "data": {"message": "Profile updated"}}