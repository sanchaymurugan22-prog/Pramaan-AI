"""Pramaan AI backend: the FastAPI app. All route files are mounted here.

Run (from the backend/ folder):
    .venv/bin/uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.pipeline import runner
from app.routes import jobs, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On start: create any missing database tables, then carry on with jobs that were
    # still running when the server last stopped.
    init_db()
    runner.resume_unfinished()
    yield


app = FastAPI(title="Pramaan AI", version="0.2.0", lifespan=lifespan)

# The React dev server (port 5173) proxies /api to us, but allow it directly too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(jobs.router)
