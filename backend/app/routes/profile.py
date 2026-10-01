"""Profile & settings (Stage 9B, design 41): everyone's own language and preferences.

GET /api/profile     me (as /api/auth/me) plus the choices for the forms
PUT /api/profile     {"language": "hi", "prefs": {...}}  only these; name, employee ID, email, division and
                     role are changed by an Admin (Users & access), so nobody can give themselves another identity.

prefs (all optional):
  text_size        normal | large | xlarge        (the whole app's text size)
  high_contrast    true | false                   (darker text and borders)
  output_languages ["en", "hi", ...]              (ticked in advance once translation arrives in Stage 8)
  notify_ready, notify_sent_back, notify_watch    true | false (in-app notifications; default on)

GET /api/auth/options   (no sign-in) the languages and divisions, for the language and request-access screens
GET /api/auth/computer  (no sign-in, only before First-time setup) memory, processors, disk and AI mode
"""

import os
import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import audit
from app.ai import llm
from app.auth import accounts
from app.auth.deps import signed_in
from app.config import settings
from app.db import User, get_session
from app.routes.auth import user_json

router = APIRouter(prefix="/api", tags=["profile"])

TEXT_SIZES = ("normal", "large", "xlarge")
NOTIFY_KEYS = ("notify_ready", "notify_sent_back", "notify_watch")


def options() -> dict:
    return {"languages": [{"code": code, "name": name} for code, name in accounts.LANGUAGES.items()],
            "divisions": accounts.DIVISIONS}


@router.get("/auth/options")
def public_options():
    return options()


@router.get("/auth/computer")
def this_computer(db: Session = Depends(get_session)):
    """For design 07 "This computer is ready": real numbers, read from this computer. Open without signing
    in, so it is only answered while there is no account at all (before First-time setup)."""
    if not accounts.needs_setup(db):
        raise HTTPException(409, "Setup is already done.")
    disk = shutil.disk_usage(settings.data_dir)
    try:
        memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        memory = None
    return {
        "memory_bytes": memory,
        "processors": os.cpu_count(),
        "disk_free_bytes": disk.free,
        "ai": llm.describe() | {"label": {"local": "Sarvam 30B on this computer", "cloud": "Sarvam cloud (development only)",
                                          "mock": "Mock AI (test answers, no model)"}.get(settings.ai_mode, settings.ai_mode)},
    }


@router.get("/profile")
def get_profile(user: User = Depends(signed_in)):
    return {"user": user_json(user), **options()}


class ProfileChange(BaseModel):
    language: str | None = None
    prefs: dict | None = None


def clean_prefs(old: dict, new: dict) -> dict:
    prefs = dict(old or {})
    for key, value in new.items():
        if key == "text_size":
            if value not in TEXT_SIZES:
                raise HTTPException(400, "Text size must be normal, large or xlarge.")
            prefs[key] = value
        elif key == "high_contrast" or key in NOTIFY_KEYS:
            prefs[key] = bool(value)
        elif key == "output_languages":
            if not isinstance(value, list) or not value or any(v not in accounts.LANGUAGES for v in value):
                raise HTTPException(400, "Choose at least one output language from the list.")
            prefs[key] = list(dict.fromkeys(value))[:23]
        else:
            raise HTTPException(400, f"Unknown setting: {key}")
    return prefs


@router.put("/profile")
def change_profile(change: ProfileChange, db: Session = Depends(get_session), user: User = Depends(signed_in)):
    words = []
    if change.language is not None:
        try:
            language = accounts.clean_language(change.language)
        except accounts.AccountError as exc:
            raise HTTPException(400, str(exc))
        if language != user.language:
            words.append(f"language {accounts.LANGUAGES.get(user.language or 'en')} → {accounts.LANGUAGES[language]}")
            user.language = language
    if change.prefs is not None:
        prefs = clean_prefs(user.prefs or {}, change.prefs)
        if prefs != (user.prefs or {}):
            words.append("preferences")
            user.prefs = prefs  # a new dict, so SQLAlchemy saves it
    db.commit()
    if words:
        audit.log("users", "profile_changed", f"Changed their {', '.join(words)}", actor=user,
                  target=f"user {user.username}")
    return {"user": user_json(user)}
