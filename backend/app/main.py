"""SchoolAssist API - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .database import SessionLocal, sync_schema
from .routers import (
    academics,
    auth,
    chat,
    dashboard,
    exports,
    leaves,
    marksheets,
    operations,
    organizations,
    reports,
    school_management,
    tests,
    worksheets,
)
from .services.seed import seed_subscription_plans

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables + missing columns (fine for MVP; switch to Alembic in production)
    sync_schema()
    db = SessionLocal()
    try:
        seed_subscription_plans(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "SchoolAssist - Pakistan school-focused teacher assistant SaaS. "
        "Multi-tenant (schools and individual teachers) with worksheet/test "
        "generation, marksheets, reports and a Qwen-powered AI assistant."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(organizations.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(academics.router, prefix=settings.API_PREFIX)
app.include_router(worksheets.router, prefix=settings.API_PREFIX)
app.include_router(tests.router, prefix=settings.API_PREFIX)
app.include_router(marksheets.router, prefix=settings.API_PREFIX)
app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(exports.router, prefix=settings.API_PREFIX)
app.include_router(chat.router, prefix=settings.API_PREFIX)
app.include_router(operations.router, prefix=settings.API_PREFIX)
app.include_router(leaves.router, prefix=settings.API_PREFIX)
app.include_router(school_management.router, prefix=settings.API_PREFIX)


@app.get(f"{settings.API_PREFIX}/health")
def health():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "qwen_configured": bool(settings.DASHSCOPE_API_KEY),
        # Misconfiguration guard: "sqlite" in production means the
        # DATABASE_URL secret is missing on this server.
        "database": "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgres",
    }


@app.get("/")
def root():
    return {"service": settings.PROJECT_NAME, "docs": "/docs", "health": f"{settings.API_PREFIX}/health"}
