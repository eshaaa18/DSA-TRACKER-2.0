from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, field_validator


# ================= AUTH =================
class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=30,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="3–30 chars, letters/numbers/underscore/hyphen only",
        examples=["alice_dev"],
    )
    email: EmailStr = Field(description="Valid email address", examples=["alice@example.com"])
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Min 8 chars, must have uppercase, lowercase and digit",
        examples=["Secure123"],
    )
    role: str = Field(
        default="student",
        description="Either 'student' or 'admin'",
        examples=["student"],
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        return v if v in {"student", "admin"} else "student"

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Registered email", examples=["alice@example.com"])
    password: str = Field(description="Account password", examples=["Secure123"])


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(description="Current password", examples=["OldPass1"])
    new_password: str = Field(
        min_length=8,
        description="New password (uppercase + lowercase + digit)",
        examples=["NewPass2"],
    )

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UpdateProfileRequest(BaseModel):
    bio: Optional[str] = Field(default=None, max_length=500, examples=["CS student @ KIIT"])
    github_url: Optional[str] = Field(default=None, max_length=200, examples=["https://github.com/alice"])
    linkedin_url: Optional[str] = Field(default=None, max_length=200, examples=["https://linkedin.com/in/alice"])
    leetcode_username: Optional[str] = Field(default=None, max_length=50, examples=["alice_lc"])


# ================= PROBLEMS =================
class CreateProblemRequest(BaseModel):
    title: str = Field(description="Problem title", examples=["Two Sum"])
    topic: str = Field(description="Topic/category", examples=["Arrays & Hashing"])
    difficulty: str = Field(description="Easy / Medium / Hard", examples=["Easy"])
    description: str = Field(default="", examples=["Given an array of integers..."])
    leetcode_slug: str = Field(default="", examples=["two-sum"])
    tags: List[str] = Field(default=[], examples=[["Array", "Hash Table"]])

    @field_validator("difficulty")
    @classmethod
    def valid_difficulty(cls, v: str) -> str:
        if v not in {"Easy", "Medium", "Hard"}:
            raise ValueError("difficulty must be Easy/Medium/Hard")
        return v


class UpdateProblemRequest(BaseModel):
    title: Optional[str] = Field(default=None, examples=["Two Sum"])
    description: Optional[str] = Field(default=None, examples=["Updated description"])
    topic: Optional[str] = Field(default=None, examples=["Arrays & Hashing"])
    difficulty: Optional[str] = Field(default=None, examples=["Medium"])
    leetcode_slug: Optional[str] = Field(default=None, examples=["two-sum"])
    tags: Optional[List[str]] = Field(default=None, examples=[["Array"]])


# ================= SUBMISSIONS =================
VALID_STATUSES = {
    "Accepted", "Wrong Answer", "Time Limit Exceeded",
    "Runtime Error", "Memory Limit Exceeded", "Compilation Error",
}


class SubmitRequest(BaseModel):
    problem_id: int = Field(description="ID of the problem", examples=[1])
    status: str = Field(
        description="Submission status",
        examples=["Accepted"],
    )
    language: str = Field(default="Unknown", examples=["Python"])
    time_ms: int = Field(default=0, examples=[120])
    memory_kb: int = Field(default=0, examples=[18000])
    notes: str = Field(default="", examples=["Used hashmap approach"])

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return v


# ================= LEETCODE SYNC =================
class LCSyncItem(BaseModel):
    slug: str = Field(description="LeetCode problem slug", examples=["two-sum"])
    title: str = Field(default="", examples=["Two Sum"])
    difficulty: str = Field(default="Unknown", examples=["Easy"])


class LCSyncRequest(BaseModel):
    solved: List[LCSyncItem] = Field(
        description="List of solved LeetCode problems",
        examples=[[{"slug": "two-sum", "title": "Two Sum", "difficulty": "Easy"}]],
    )


# ================= NOTES =================
class CreateNoteRequest(BaseModel):
    title: str = Field(description="Note title", examples=["Two Sum approach"])
    content: str = Field(description="Note content / solution explanation", examples=["Use a hashmap to store complements..."])
    topic: str = Field(default="", examples=["Arrays & Hashing"])
    pinned: bool = Field(default=False, examples=[False])
    problem_id: Optional[int] = Field(default=None, examples=[1])
    tags: List[str] = Field(default=[], examples=[["hashmap", "easy"]])


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = Field(default=None, examples=["Updated title"])
    content: Optional[str] = Field(default=None, examples=["Updated content"])
    topic: Optional[str] = Field(default=None, examples=["Arrays & Hashing"])
    pinned: Optional[bool] = Field(default=None, examples=[True])
    tags: Optional[List[str]] = Field(default=None, examples=[["hashmap"]])


# ================= ACADEMIC =================
class UpsertAcademicRequest(BaseModel):
    user_id: int = Field(description="Target user ID", examples=[1])
    cgpa: float = Field(description="CGPA out of 10", examples=[8.5])
    attendance: int = Field(description="Attendance percentage", examples=[85])
    semester: str = Field(default="", examples=["6th"])
    branch: str = Field(default="", examples=["CSE"])


class SetRoleRequest(BaseModel):
    role: str = Field(description="New role: student or admin", examples=["student"])

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in {"student", "admin"}:
            raise ValueError("role must be 'student' or 'admin'")
        return v


# ================= RESPONSE MODELS =================
class BaseResponse(BaseModel):
    success: bool


class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    role: str


class RegisterData(BaseModel):
    token: str
    user: UserResponse


class RegisterResponse(BaseResponse):
    data: RegisterData


class LoginData(BaseModel):
    token: str
    user: UserResponse


class LoginResponse(BaseResponse):
    data: LoginData