"""Sign-in page routes (Stage 6B). These work WITHOUT being signed in:

GET  /api/auth/status          does the app need First-time setup? who is signed in (if anyone)?
POST /api/auth/setup           First-time setup: make the first Admin (only while there are no users)
POST /api/auth/request-access  "Request access": ask an Admin for an Operator or Reviewer account
POST /api/auth/forgot          "Forgot password": ask an Admin to set a temporary password
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import accounts
from app.auth.accounts import ROLE_LABELS, AccountError
from app.db import User, get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_json(user: User) -> dict:
    """What the web page may know about the signed-in user (never the password hash)."""
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": ROLE_LABELS[user.role],
        "must_change_password": user.must_change_password,
    }


@router.get("/status")
def status(db: Session = Depends(get_session)):
    return {"needs_setup": accounts.needs_setup(db), "user": None}


class SetupForm(BaseModel):
    username: str
    full_name: str
    password: str


@router.post("/setup", status_code=201)
def setup(form: SetupForm, db: Session = Depends(get_session)):
    """Only works while there are no users at all. Afterwards: 409."""
    if not accounts.needs_setup(db):
        raise HTTPException(409, "Setup is already done. Sign in, or ask your Admin for an account.")
    try:
        user = accounts.create_first_admin(db, form.username, form.full_name, form.password)
    except AccountError as exc:
        raise HTTPException(409 if "already done" in str(exc) else 400, str(exc))
    return {"user": user_json(user)}


class AccessForm(BaseModel):
    username: str
    full_name: str
    role: str
    reason: str
    password: str


@router.post("/request-access", status_code=201)
def request_access(form: AccessForm, db: Session = Depends(get_session)):
    if accounts.needs_setup(db):
        raise HTTPException(409, "This computer is not set up yet. The first Admin must finish First-time setup.")
    try:
        request = accounts.request_access(db, form.username, form.full_name, form.role, form.reason, form.password)
    except AccountError as exc:
        raise HTTPException(400, str(exc))
    return {"username": request.username, "full_name": request.full_name, "role": request.role,
            "role_label": ROLE_LABELS[request.role], "created_at": request.created_at.isoformat()}


class ForgotForm(BaseModel):
    username: str
    message: str = ""


@router.post("/forgot", status_code=202)
def forgot(form: ForgotForm, db: Session = Depends(get_session)):
    """Always the same answer, so it cannot be used to find out which usernames exist."""
    try:
        accounts.request_reset(db, form.username, form.message)
    except AccountError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "message": "Request sent. Your Admin will check who you are and give you a temporary password."}
