from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

# Routers
from authentication import router as auth_router
from academic import router as academic_router
from notes import router as notes_router
from problems import router as problems_router
from submissions import router as submissions_router
from recommendations import router as recs_router

from loggings import configure_logging
from database import Database

# ================= INIT =================

configure_logging()

app = FastAPI(
    title="DSA Tracker API",
    description="""
## DSA Tracker Backend
Track your Data Structures & Algorithms progress with this API.
""",
    version="1.0.0",
)

# ✅ FIXED: now app exists before using it
@app.on_event("startup")
async def startup():
    print("🚀 Initializing Database...")
    Database()


# ================= OPENAPI =================

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    schema.setdefault("components", {})
    schema["components"].setdefault("securitySchemes", {})

    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict):
                operation.setdefault("security", [{"BearerAuth": []}])

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


# ================= CORS =================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= ERROR HANDLER =================

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()   # 🔥 FULL ERROR STACK
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),   # show real error
        },
    )
@app.get("/crash")
async def crash():
    1 / 0   # force error

# ================= ROUTERS =================

app.include_router(auth_router, prefix="/api/auth")
app.include_router(academic_router, prefix="/api")
app.include_router(notes_router, prefix="/api")
app.include_router(problems_router, prefix="/api/problems")
app.include_router(submissions_router, prefix="/api")
app.include_router(recs_router, prefix="/api")


# ================= HEALTH =================

@app.get("/health")
async def health():
    return {"status": "ok"}