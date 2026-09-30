"""Pramaan AI backend: the FastAPI app. All route files are mounted here.

Run (from the backend/ folder):
    .venv/bin/uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import system

app = FastAPI(title="Pramaan AI", version="0.1.0")

# The React dev server (port 5173) proxies /api to us, but allow it directly too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
