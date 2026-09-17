from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime, timezone
import asyncio
import uuid
import logging
from typing import Optional, Dict, Any, List

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
from app.api.v1.categories import router as categories_router
from app.api.v1.connections import router as connections_router, integrations_router as google_integrations_router
from app.api.v1.team import router as team_router
from app.api.v1.serp import router as serp_router
from app.api.v1.admin_ai import router as admin_ai_router

logger = logging.getLogger("locallift")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="LocalLift — Local SEO Management & Automation Operating System"
)

# CORS Configuration
origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else []

if settings.ENVIRONMENT.lower() == "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

import time

@app.middleware("http")
async def action_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    request.state.request_id = req_id

    path = request.url.path
    is_asset = path.startswith("/static") or path.endswith((".js", ".css", ".ico", ".png", ".jpg"))

    start_time = time.time()
    if not is_asset:
        logger.info(f"[API_START] request_id={req_id} method={request.method} path={path}")

    try:
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Request-ID"] = req_id
        if not is_asset:
            logger.info(f"[API_END] request_id={req_id} status={response.status_code} duration_ms={duration_ms}")
        return response
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        if not is_asset:
            logger.error(f"[API_END] request_id={req_id} status=500 duration_ms={duration_ms} error={str(exc)}")
        raise exc

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(categories_router, prefix=settings.API_V1_STR)
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
app.include_router(connections_router, prefix=settings.API_V1_STR)
app.include_router(google_integrations_router, prefix=settings.API_V1_STR)
app.include_router(team_router, prefix=settings.API_V1_STR)
app.include_router(serp_router, prefix=settings.API_V1_STR)
app.include_router(admin_ai_router, prefix=settings.API_V1_STR)

def _is_allowed_origin(origin: Optional[str]) -> bool:
    if not origin:
        return False
    clean_origin = origin.rstrip("/")
    if clean_origin in origins:
        return True
    if settings.ENVIRONMENT.lower() != "production":
        return True
    return False

def _add_cors_headers(request: Request, headers: dict = None) -> dict:
    h = dict(headers or {})
    origin = request.headers.get("origin")
    if origin and _is_allowed_origin(origin):
        h["Access-Control-Allow-Origin"] = origin
        h["Access-Control-Allow-Credentials"] = "true"
        h["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        h["Access-Control-Allow-Headers"] = "*"
    return h

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = str(uuid.uuid4())[:8]
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "detail": exc.detail,
            "request_id": req_id
        },
        headers=_add_cors_headers(request, getattr(exc, "headers", None))
    )

from fastapi.encoders import jsonable_encoder

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    clean_errors = jsonable_encoder(exc.errors(), custom_encoder={ValueError: str, Exception: str})
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": "Invalid request parameters.",
            "detail": clean_errors,
            "request_id": req_id
        },
        headers=_add_cors_headers(request)
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = str(uuid.uuid4())[:8]
    logger.exception(f"Unhandled server error [ReqID: {req_id}]: {exc}")
    
    is_prod = settings.ENVIRONMENT.lower() == "production"
    safe_detail = "Internal server error." if is_prod else str(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please contact support or check server logs.",
            "detail": safe_detail,
            "request_id": req_id
        },
        headers=_add_cors_headers(request)
    )

@app.on_event("startup")
async def startup_event():
    import app.models  # noqa: F401
    from app.core.migrations import run_db_migrations
    from app.services.scheduler import start_scheduler
    settings.validate_production_security()
    await asyncio.to_thread(run_db_migrations)
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    from app.services.scheduler import stop_scheduler
    stop_scheduler()

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
