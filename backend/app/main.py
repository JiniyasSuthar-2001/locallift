from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import asyncio

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.api.v1.auth import router as auth_router
from app.api.v1.projects import router as projects_router
from app.api.v1.audits import router as audits_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.gbp import router as gbp_router, google_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.local_seo import router as local_seo_router
from app.api.v1.ai import router as ai_router
from app.api.v1.reports import router as reports_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.templates import router as templates_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="LocalLift — Local SEO Management & Automation Operating System"
)

# CORS
origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(audits_router, prefix=settings.API_V1_STR)
app.include_router(tasks_router, prefix=settings.API_V1_STR)
app.include_router(gbp_router, prefix=settings.API_V1_STR)
app.include_router(google_router, prefix=settings.API_V1_STR)
app.include_router(keywords_router, prefix=settings.API_V1_STR)
app.include_router(local_seo_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(organizations_router, prefix=settings.API_V1_STR)
app.include_router(templates_router, prefix=settings.API_V1_STR)

def _sync_sqlite_schema(sync_conn):
    """Auto-migrate SQLite database by adding any missing table columns."""
    from sqlalchemy import inspect, text
    inspector = inspect(sync_conn)
    tables = inspector.get_table_names()
    for table_name, table in Base.metadata.tables.items():
        if table_name in tables:
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(sync_conn.dialect)
                    try:
                        sync_conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"))
                    except Exception as e:
                        print(f"Warning: Failed to auto-add column {col.name} to {table_name}: {e}")

@app.on_event("startup")
async def startup_event():
    import app.models  # noqa: F401
    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_schema)

@app.get("/")
async def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected"
    }

