import pytest
import pytest_asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "service-key")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough")


def make_app() -> FastAPI:
    app = FastAPI()
    import authentication as auth_module
    import submissions as sub_module
    import notes as notes_module
    import problems as problems_module
    import academic as academic_module

    app.include_router(auth_module.router, prefix="/api/auth")
    app.include_router(sub_module.router, prefix="/api")
    app.include_router(notes_module.router, prefix="/api")
    app.include_router(problems_module.router, prefix="/api/problems")
    app.include_router(academic_module.router, prefix="/api")

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": str(exc.errors()), "code": "VALIDATION_ERROR"},
        )

    return app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _mock_db_response(json_data, status: int = 200):
    import database
    import json as _json
    return database.DBResponse(status=status, body=_json.dumps(json_data))


def _make_token(user_id: int = 1, role: str = "student") -> str:
    import auth
    token, _ = auth.JWTHandler.generate(user_id, "testuser", "test@example.com", role)
    return token


def _admin_token() -> str:
    return _make_token(user_id=99, role="admin")


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            mock_db.POST = AsyncMock(side_effect=[
                _mock_db_response([{"user_id": 42, "username": "alice", "email": "alice@example.com", "role": "student"}], 201),
                _mock_db_response([{}], 201),
            ])
            response = await client.post("/api/auth/register", json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "Secure123",
            })
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "token" in data["data"]

    @pytest.mark.asyncio
    async def test_register_duplicate_user(self, client):
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{"user_id": 1}]))
            response = await client.post("/api/auth/register", json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "Secure123",
            })
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password_no_uppercase(self, client):
        response = await client.post("/api/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "weakpassword1",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_no_digit(self, client):
        response = await client.post("/api/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "WeakPassword",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        response = await client.post("/api/auth/register", json={
            "username": "alice",
            "email": "not-an-email",
            "password": "Secure123",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_username(self, client):
        response = await client.post("/api/auth/register", json={
            "username": "ab",
            "email": "alice@example.com",
            "password": "Secure123",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username_chars(self, client):
        response = await client.post("/api/auth/register", json={
            "username": "alice!@#",
            "email": "alice@example.com",
            "password": "Secure123",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_db_failure_returns_500(self, client):
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            mock_db.POST = AsyncMock(return_value=_mock_db_response({}, status=500))
            response = await client.post("/api/auth/register", json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "Secure123",
            })
        assert response.status_code == 500


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        import security
        pw_hash = security.Password.hash("Secure123")
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{
                "user_id": 1, "username": "alice", "email": "alice@example.com",
                "role": "student", "password_hash": pw_hash,
            }]))
            mock_db.PATCH = AsyncMock(return_value=_mock_db_response({}))
            response = await client.post("/api/auth/login", json={
                "email": "alice@example.com",
                "password": "Secure123",
            })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data["data"]
        assert "password_hash" not in str(data)

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        import security
        pw_hash = security.Password.hash("Secure123")
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{
                "user_id": 1, "username": "alice", "email": "alice@example.com",
                "role": "student", "password_hash": pw_hash,
            }]))
            response = await client.post("/api/auth/login", json={
                "email": "alice@example.com",
                "password": "WrongPass1",
            })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.post("/api/auth/login", json={
                "email": "ghost@example.com",
                "password": "Secure123",
            })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        response = await client.post("/api/auth/login", json={"email": "alice@example.com"})
        assert response.status_code == 422


class TestAuthMiddleware:
    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_returns_401(self, client):
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix_returns_401(self, client):
        token = _make_token()
        response = await client.get("/api/auth/me", headers={"Authorization": token})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_passes_middleware(self, client):
        token = _make_token(user_id=1)
        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{
                "user_id": 1, "username": "testuser", "email": "test@example.com", "role": "student",
            }]))
            response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_logout_blacklists_token(self, client):
        token = _make_token(user_id=1)
        response = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        with patch("authentication.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{"user_id": 1}]))
            response2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response2.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_message(self, client):
        token = _make_token(user_id=1)
        response = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert response.json()["data"]["message"] == "Logged out successfully"


class TestAdminGuards:
    @pytest.mark.asyncio
    async def test_student_cannot_access_admin_overview(self, client):
        token = _make_token(user_id=1, role="student")
        with patch("academic.db") as mock_db:
            mock_db.RPC = AsyncMock(return_value=_mock_db_response({}))
            response = await client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_list_all_students(self, client):
        token = _make_token(user_id=1, role="student")
        response = await client.get("/api/admin/students", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_change_role(self, client):
        token = _make_token(user_id=1, role="student")
        response = await client.patch(
            "/api/admin/users/2/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_access_other_academic(self, client):
        token = _make_token(user_id=1, role="student")
        with patch("academic.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.get("/api/academic/99", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_can_access_own_academic(self, client):
        token = _make_token(user_id=1, role="student")
        with patch("academic.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{
                "user_id": 1, "cgpa": 8.5, "attendance_percentage": 90,
            }]))
            response = await client.get("/api/academic/1", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_list_all_students(self, client):
        token = _admin_token()
        with patch("academic.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.get("/api/admin/students", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_set_role_invalid_value(self, client):
        token = _admin_token()
        response = await client.patch(
            "/api/admin/users/2/role",
            json={"role": "superuser"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestNotes:
    @pytest.mark.asyncio
    async def test_create_note_success(self, client):
        token = _make_token(user_id=1)
        with patch("notes.db") as mock_db:
            mock_db.POST = AsyncMock(return_value=_mock_db_response([{
                "note_id": 1, "title": "My Note", "content": "Hello world",
            }], 201))
            response = await client.post(
                "/api/notes",
                json={"title": "My Note", "content": "Hello world"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_note_missing_title(self, client):
        token = _make_token(user_id=1)
        response = await client.post(
            "/api/notes",
            json={"content": "some content"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_note_missing_content(self, client):
        token = _make_token(user_id=1)
        response = await client.post(
            "/api/notes",
            json={"title": "only title"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_note_not_found(self, client):
        token = _make_token(user_id=1)
        with patch("notes.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.get("/api/notes/999", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_search_notes_requires_q(self, client):
        token = _make_token(user_id=1)
        response = await client.get("/api/notes/search", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_note_nothing_to_update(self, client):
        token = _make_token(user_id=1)
        response = await client.patch(
            "/api/notes/1",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_toggle_pin_not_found(self, client):
        token = _make_token(user_id=1)
        with patch("notes.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.post("/api/notes/999/pin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 404


class TestSubmissions:
    @pytest.mark.asyncio
    async def test_submit_accepted(self, client):
        token = _make_token(user_id=1)
        with patch("submissions.db") as mock_db:
            mock_db.GET = AsyncMock(side_effect=[
                _mock_db_response([{"problem_id": 1}]),
                _mock_db_response([{"current_streak": 5, "longest_streak": 10}]),
            ])
            mock_db.POST = AsyncMock(return_value=_mock_db_response([{"submission_id": 1, "status": "Accepted"}], 201))
            mock_db.RPC = AsyncMock(return_value=_mock_db_response({}))
            response = await client.post(
                "/api/submit",
                json={"problem_id": 1, "status": "Accepted", "language": "Python"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 201
        assert response.json()["data"]["message"] == "Accepted!"

    @pytest.mark.asyncio
    async def test_submit_wrong_answer(self, client):
        token = _make_token(user_id=1)
        with patch("submissions.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([{"problem_id": 1}]))
            mock_db.POST = AsyncMock(return_value=_mock_db_response([{"submission_id": 2, "status": "Wrong Answer"}], 201))
            response = await client.post(
                "/api/submit",
                json={"problem_id": 1, "status": "Wrong Answer", "language": "Python"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 201
        assert response.json()["data"]["message"] == "Submission recorded"

    @pytest.mark.asyncio
    async def test_submit_invalid_status(self, client):
        token = _make_token(user_id=1)
        response = await client.post(
            "/api/submit",
            json={"problem_id": 1, "status": "INVALID_STATUS", "language": "Python"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_problem_not_found(self, client):
        token = _make_token(user_id=1)
        with patch("submissions.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.post(
                "/api/submit",
                json={"problem_id": 9999, "status": "Accepted", "language": "Python"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_performance_forbidden_for_other_user(self, client):
        token = _make_token(user_id=1, role="student")
        response = await client.get("/api/performance/2", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_performance_allowed_for_own_user(self, client):
        token = _make_token(user_id=1, role="student")
        with patch("submissions.db") as mock_db:
            mock_db.GET = AsyncMock(return_value=_mock_db_response([]))
            response = await client.get("/api/performance/1", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_lc_sync_bulk_single_request(self, client):
        token = _make_token(user_id=1)
        with patch("submissions.db") as mock_db:
            mock_db.POST = AsyncMock(return_value=_mock_db_response([{}, {}], 201))
            response = await client.post(
                "/api/leetcode/sync",
                json={"solved": [
                    {"slug": "two-sum", "title": "Two Sum", "difficulty": "Easy"},
                    {"slug": "add-two-numbers", "title": "Add Two Numbers", "difficulty": "Medium"},
                ]},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert mock_db.POST.call_count == 1

        assert response.status_code == 200
        assert response.json()["data"]["synced"] == 2

    @pytest.mark.asyncio
    async def test_lc_sync_empty_list(self, client):
        token = _make_token(user_id=1)
        response = await client.post(
            "/api/leetcode/sync",
            json={"solved": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["synced"] == 0


class TestSecurity:
    def test_hash_and_verify_roundtrip(self):
        import security
        pw = "MyPassword9"
        assert security.Password.verify(pw, security.Password.hash(pw)) is True

    def test_wrong_password_fails_verify(self):
        import security
        pw_hash = security.Password.hash("MyPassword9")
        assert security.Password.verify("WrongPass1", pw_hash) is False

    def test_different_passwords_produce_different_hashes(self):
        import security
        h1 = security.Password.hash("Password1")
        h2 = security.Password.hash("Password1")
        assert h1 != h2

    def test_hash_has_salt_separator(self):
        import security
        h = security.Password.hash("Password1")
        assert "$" in h
        salt, _ = h.split("$", 1)
        assert len(salt) == 32

    def test_rate_limiter_blocks_at_limit(self):
        import security
        rl = security.RateLimiter()
        for _ in range(5):
            rl.allow("key_block", 5, 60)
        assert rl.allow("key_block", 5, 60) is False

    def test_rate_limiter_allows_under_limit(self):
        import security
        rl = security.RateLimiter()
        for _ in range(4):
            assert rl.allow("key_under", 5, 60) is True

    def test_rate_limiter_resets_after_window(self):
        import security
        rl = security.RateLimiter()
        for _ in range(3):
            rl.allow("key_reset", 3, 1)
        assert rl.allow("key_reset", 3, 1) is False
        time.sleep(1.1)
        assert rl.allow("key_reset", 3, 1) is True

    def test_safe_search_strips_ampersand(self):
        import security
        assert "&" not in security.Validate.safe_search("foo&role=eq.admin")

    def test_safe_search_strips_wildcard(self):
        import security
        assert "*" not in security.Validate.safe_search("foo*bar")

    def test_safe_search_strips_pipe(self):
        import security
        assert "|" not in security.Validate.safe_search("foo|bar")

    def test_sanitize_strips_script_tags(self):
        import security
        result = security.Validate.sanitize("<script>alert('xss')</script>")
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_respects_max_len(self):
        import security
        result = security.Validate.sanitize("a" * 1000, max_len=100)
        assert len(result) <= 100


class TestJWT:
    def test_generate_and_verify(self):
        import auth
        token, jti = auth.JWTHandler.generate(1, "user", "u@e.com", "student")
        payload = auth.JWTHandler.verify(token)
        assert payload is not None
        assert payload.user_id == 1
        assert payload.role == "student"
        assert payload.jti == jti

    def test_blacklisted_token_rejected(self):
        import auth
        token, jti = auth.JWTHandler.generate(2, "user2", "u2@e.com", "student")
        exp = datetime.now(timezone.utc) + timedelta(hours=24)
        auth.blacklist.revoke(jti, exp)
        assert auth.JWTHandler.verify(token) is None

    def test_tampered_token_rejected(self):
        import auth
        token, _ = auth.JWTHandler.generate(1, "user", "u@e.com", "student")
        tampered = token[:-5] + "XXXXX"
        assert auth.JWTHandler.verify(tampered) is None

    def test_token_payload_fields(self):
        import auth
        token, _ = auth.JWTHandler.generate(42, "alice", "alice@test.com", "admin")
        payload = auth.JWTHandler.verify(token)
        assert payload.user_id == 42
        assert payload.username == "alice"
        assert payload.email == "alice@test.com"
        assert payload.role == "admin"

    def test_blacklist_purges_expired_entries(self):
        import auth
        _, jti = auth.JWTHandler.generate(99, "x", "x@x.com", "student")
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        auth.blacklist.revoke(jti, past)
        assert not auth.blacklist.is_revoked(jti)