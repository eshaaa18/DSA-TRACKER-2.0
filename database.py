from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

# ✅ Load env early
load_dotenv()


# ================= RESPONSE =================
@dataclass
class DBResponse:
    status: int
    body: str
    json: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            import json
            self.json = json.loads(self.body)
        except Exception:
            self.json = {}

    def ok(self) -> bool:
        return 200 <= self.status < 300


# ================= DATABASE =================
class Database:
    _instance: "Database | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "Database":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init()
                    cls._instance = inst
        return cls._instance

    def _init(self) -> None:
        # 🔥 FORCE LOAD AGAIN (safety)
        load_dotenv()

        self.url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.service_key = os.getenv("SUPABASE_SERVICE_KEY")

        print("\n===== DATABASE INIT =====")
        print("URL:", self.url)
        print("ANON:", self.anon_key)
        print("SERVICE:", self.service_key)
        print("=========================\n")

        # 🚨 HARD FAIL (good for debugging)
        if not self.url or not self.anon_key or not self.service_key:
            raise RuntimeError(
                "❌ Missing Supabase environment variables. Check your .env file"
            )

        self._client = httpx.AsyncClient(
            base_url=self.url,
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    # ================= HEADERS =================
    def _headers(self, service: bool) -> dict[str, str]:
        key = self.service_key if service else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    # ================= CORE REQUEST =================
    async def _request(
        self,
        method: str,
        path: str,
        body: Any = None,
        service: bool = False,
    ) -> DBResponse:
        try:
            resp = await self._client.request(
                method=method,
                url=path,
                headers=self._headers(service),
                json=body,
            )
        except httpx.RequestError as exc:
            raise RuntimeError(f"❌ DB request failed: {exc}") from exc

        return DBResponse(status=resp.status_code, body=resp.text)

    # ================= METHODS =================
    async def GET(self, path: str, service: bool = False) -> DBResponse:
        return await self._request("GET", path, service=service)

    async def POST(self, path: str, body: Any, service: bool = False) -> DBResponse:
        return await self._request("POST", path, body, service)

    async def PATCH(self, path: str, body: Any, service: bool = False) -> DBResponse:
        return await self._request("PATCH", path, body, service)

    async def DELETE(self, path: str, service: bool = False) -> DBResponse:
        return await self._request("DELETE", path, service=service)

    async def RPC(self, fn: str, body: Any, service: bool = True) -> DBResponse:
        return await self._request("POST", f"/rest/v1/rpc/{fn}", body, service)

    async def AUTH(self, path: str, body: Any, service: bool = False) -> DBResponse:
        return await self._request("POST", f"/auth/v1{path}", body, service)

    async def close(self) -> None:
        await self._client.aclose()