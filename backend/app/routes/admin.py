"""Admin routes (Stage 6B). Only Admins; Admins do not see or approve job content.

GET  /api/admin/users                        every user (never the password hash)
POST /api/admin/users                        add a user: {"username", "full_name", "role"} -> a temporary password, shown once
PUT  /api/admin/users/{id}                   change name / role / switch on or off / unlock
POST /api/admin/users/{id}/reset-password    a new temporary password, shown once (must be changed at next sign-in)

GET  /api/admin/requests                     access requests and "forgot password" requests
POST /api/admin/requests/{id}/approve        make the account (optionally with another role: {"role": "reviewer"})
POST /api/admin/requests/{id}/reject
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import accounts, sessions
from app.auth.accounts import ROLE_LABELS, AccountError
from app.auth.deps import allow
from app.db import AccountRequest, User, get_session
from app.routes.jobs import _time

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = allow("admin")


def admin_user_json(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": ROLE_LABELS[user.role],
        "is_active": user.is_active,
        "locked": accounts.is_locked(user),
        "must_change_password": user.must_change_password,
        "failed_attempts": user.failed_attempts,
        "created_at": _time(user.created_at),
        "last_login": _time(user.last_login),
    }


def request_json(db: Session, request: AccountRequest) -> dict:
    decided_by = db.get(User, request.decided_by) if request.decided_by else None
    return {
        "id": request.id,
        "kind": request.kind,
        "username": request.username,
        "full_name": request.full_name,
        "role": request.role,
        "role_label": ROLE_LABELS.get(request.role or "", ""),
        "reason": request.reason,
        "status": request.status,
        # reset requests: does this username exist? (the person asking was not told)
        "user_exists": accounts.find_user(db, request.username) is not None,
        "created_at": _time(request.created_at),
        "decided_at": _time(request.decided_at),
        "decided_by": decided_by.full_name if decided_by else None,
    }


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, f"User {user_id} not found.")
    return user


@router.get("/users")
def list_users(db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    return [admin_user_json(u) for u in db.scalars(select(User).order_by(User.full_name))]


class NewUser(BaseModel):
    username: str
    full_name: str
    role: str


@router.post("/users", status_code=201)
def add_user(form: NewUser, db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    try:
        user, temporary = accounts.create_user(db, admin, form.username, form.full_name, form.role)
    except AccountError as exc:
        raise HTTPException(400, str(exc))
    # The only time this password is ever shown. It is not stored anywhere (only its hash).
    return {"user": admin_user_json(user), "temporary_password": temporary}


class UserChange(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    unlock: bool = False


@router.put("/users/{user_id}")
def change_user(user_id: int, form: UserChange, db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    user = _get_user(db, user_id)
    try:
        accounts.update_user(db, admin, user, full_name=form.full_name, role=form.role,
                             is_active=form.is_active, unlock=form.unlock)
    except AccountError as exc:
        raise HTTPException(400, str(exc))
    if not user.is_active:
        sessions.end_all(db, user.id)  # signed out everywhere, straight away
    return admin_user_json(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    user = _get_user(db, user_id)
    if user.id == admin.id:
        raise HTTPException(400, "Change your own password from your profile instead.")
    temporary = accounts.reset_password(db, admin, user)
    sessions.end_all(db, user.id)
    return {"user": admin_user_json(user), "temporary_password": temporary}


@router.get("/requests")
def list_requests(db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    rows = db.scalars(select(AccountRequest).order_by(AccountRequest.id.desc()).limit(200))
    return [request_json(db, r) for r in rows]


def _get_request(db: Session, request_id: int) -> AccountRequest:
    request = db.get(AccountRequest, request_id)
    if request is None:
        raise HTTPException(404, f"Request {request_id} not found.")
    return request


class Approval(BaseModel):
    role: str | None = None


@router.post("/requests/{request_id}/approve")
def approve_request(request_id: int, form: Approval, db: Session = Depends(get_session),
                    admin: User = Depends(admin_only)):
    request = _get_request(db, request_id)
    if request.kind != "access":
        raise HTTPException(400, "For a forgotten password, use “Reset password” on the user instead.")
    try:
        user = accounts.approve_access(db, request, admin, form.role)
    except AccountError as exc:
        raise HTTPException(409, str(exc))
    return {"request": request_json(db, request), "user": admin_user_json(user)}


@router.post("/requests/{request_id}/reject")
def reject_request(request_id: int, db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    request = _get_request(db, request_id)
    try:
        accounts.reject_request(db, request, admin)
    except AccountError as exc:
        raise HTTPException(409, str(exc))
    return {"request": request_json(db, request)}
