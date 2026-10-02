"""Pramaan AI backend: the FastAPI app. All route files are mounted here.

Run (from the backend/ folder):
    .venv/bin/uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import watch
from app.config import settings
from app.db import init_db
from app.pipeline import runner
from app.routes import admin, admin_files, admin_system, alerts, auth, comments, dashboard, jobs, languages, notifications, outputs, profile, records, review, safety, search, system, watch as watch_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On start: create any missing database tables, then carry on with jobs that were
    # still running when the server last stopped.
    init_db()
    runner.resume_unfinished()
    watch.start_timer()  # Stage 9A: new files in watch folders become draft jobs
    yield
    watch.stop_timer()


app = FastAPI(title="Pramaan AI", version="0.9.0", lifespan=lifespan)

# The React dev server (port 5173) proxies /api to us, but allow it directly too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_of(url: str | None) -> str | None:
    """"http://localhost:5173/some/page" -> "http://localhost:5173"."""
    if not url:
        return None
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None


@app.middleware("http")
async def check_origin(request: Request, call_next):
    """Every request that changes something must come from one of our own pages (ALLOWED_ORIGINS).
    Browsers always say which page sent a POST/PUT/DELETE (the Origin header, or at least Referer),
    and another website cannot fake it. Together with the SameSite=Strict cookie this stops
    "cross-site request forgery": a web page in another tab making the app do things as you."""
    if request.method in CHANGING_METHODS and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin") or _origin_of(request.headers.get("referer"))
        if origin is None or origin.rstrip("/") not in settings.allowed_origins:
            return JSONResponse({"detail": "Refused: this request did not come from a Pramaan AI page."},
                                status_code=403)
    return await call_next(request)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(outputs.router)
app.include_router(safety.router)
app.include_router(review.router)
app.include_router(admin.router)
app.include_router(records.router)
app.include_router(records.admin_router)
app.include_router(records.checker_router)
app.include_router(notifications.router)
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(watch_routes.router)
app.include_router(alerts.router)
app.include_router(profile.router)
app.include_router(comments.router)
app.include_router(admin_system.router)
app.include_router(admin_files.router)
app.include_router(languages.router)  # Stage 8
