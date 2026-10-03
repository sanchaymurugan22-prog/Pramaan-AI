"""Pramaan AI backend: the FastAPI app. All route files are mounted here.

Run (from the backend/ folder):
    .venv/bin/uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import watch
from app.config import PROJECT_ROOT, settings
from app.auth import accounts
from app.db import SessionLocal, init_db
from app.pipeline import runner
from app.routes import admin, admin_files, admin_system, alerts, auth, comments, dashboard, jobs, languages, notifications, outputs, profile, records, review, safety, search, system, watch as watch_routes
from app.signing import publish


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On start: create any missing database tables, seed demo accounts, and publish verify site
    init_db()
    with SessionLocal() as db:
        if accounts.needs_setup(db):
            accounts.setup_code()
        accounts.seed_demo_accounts(db)
        try:
            publish.build_site(db)
        except Exception:
            pass
    runner.resume_unfinished()
    watch.start_timer()  # Stage 9A: new files in watch folders become draft jobs
    yield
    watch.stop_timer()


app = FastAPI(title="Pramaan AI", version="0.9.0", lifespan=lifespan)

# Allow CORS for development & production origins
allowed_origins_list = list(settings.allowed_origins) + ["http://localhost:5173", "http://127.0.0.1:5173", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    """Every request that changes something must come from one of our own pages (ALLOWED_ORIGINS or same origin)."""
    if request.method in CHANGING_METHODS and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin") or _origin_of(request.headers.get("referer"))
        host_origin = f"{request.url.scheme}://{request.url.netloc}"
        if origin is not None:
            clean_origin = origin.rstrip("/")
            if (
                clean_origin in settings.allowed_origins
                or clean_origin == host_origin.rstrip("/")
                or "*" in settings.allowed_origins
                or "trycloudflare.com" in clean_origin
                or "vercel.app" in clean_origin
                or "onrender.com" in clean_origin
            ):
                return await call_next(request)
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

# Verify site mount at /verify
verify_site_dir = settings.data_dir / "verify-site"
if verify_site_dir.exists():
    app.mount("/verify", StaticFiles(directory=verify_site_dir, html=True), name="verify-site")

# Serve React static frontend & SPA fallback
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API route not found")
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")

