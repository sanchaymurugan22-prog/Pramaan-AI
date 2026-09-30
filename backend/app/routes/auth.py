"""Sign-in routes (Stage 6B).

These work WITHOUT being signed in:
GET  /api/auth/status          does the app need First-time setup? who is signed in (if anyone)?
POST /api/auth/setup           First-time setup: make the first Admin (only while there are no users), signed in
POST /api/auth/login           sign in: sets the session cookie
POST /api/auth/request-access  "Request access": ask an Admin for an Operator or Reviewer account
POST /api/auth/forgot          "Forgot password": ask an Admin to set a temporary password

These need a session (also while the password is a temporary one):
GET  /api/auth/me              the signed-in user
POST /api/auth/logout          sign out: deletes the session
POST /api/auth/change-password
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import audit
from app.auth import accounts, sessions
from app.auth.accounts import LOCK_AFTER_WRONG, LOCK_MINUTES, ROLE_LABELS, AccountError, SignInError
from app.auth.deps import SignedIn, current_session
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


def _set_cookie(request: Request, response: Response, token: str) -> None:
    """HttpOnly: page scripts cannot read it. SameSite=Strict: other websites cannot make the browser
    send it. Secure (HTTPS only) when the app is served over HTTPS. No expiry date: the browser forgets
    it when closed, and the server ends it after 8 hours anyway."""
    response.set_cookie(sessions.COOKIE_NAME, token, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", path="/")


def _clear_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(sessions.COOKIE_NAME, httponly=True, samesite="strict",
                           secure=request.url.scheme == "https", path="/")


@router.get("/status")
def status(request: Request, db: Session = Depends(get_session)):
    """Called when the app opens: which screen to show (setup, sign in, or the app itself)."""
    user = None
    try:
        _, user = sessions.check(db, request.cookies.get(sessions.COOKIE_NAME))
    except sessions.SessionEnded:
        pass
    return {"needs_setup": accounts.needs_setup(db), "user": user_json(user) if user else None}


class LoginForm(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(form: LoginForm, request: Request, response: Response, db: Session = Depends(get_session)):
    try:
        user = accounts.sign_in(db, form.username, form.password)
    except SignInError as refused:
        _log_refused(refused, form.username)
        # 423 Locked tells the page to show the "locked" message; everything else is 401
        raise HTTPException(423 if refused.event in ("locked", "locked_now") else 401, str(refused))
    _set_cookie(request, response, sessions.start(db, user))
    audit.log("security", "sign_in", "Signed in", actor=user, target=f"user {user.username}")
    return {"user": user_json(user)}


def _log_refused(refused: SignInError, typed_username: str) -> None:
    """A refused sign-in, for the audit trail. What was typed as the username is only written down when
    it is a real account (people sometimes type their password into the username box by mistake)."""
    user = refused.user
    if user is None:
        if refused.event == "pending":
            audit.log("security", "sign_in_refused", "Tried to sign in; the access request is still waiting",
                      actor_name=typed_username.strip().lower()[:40])
        else:
            audit.log("security", "sign_in_failed", "Failed sign-in: unknown username", actor_name="Unknown")
        return
    detail = {
        "wrong_password": f"Failed sign-in: wrong password ({user.failed_attempts} of {LOCK_AFTER_WRONG})",
        "locked_now": f"Account locked for {LOCK_MINUTES} minutes after {LOCK_AFTER_WRONG} wrong passwords",
        "locked": "Sign-in refused: the account is locked",
        "inactive": "Sign-in refused: the account is switched off",
    }[refused.event]
    action = "locked" if refused.event == "locked_now" else "sign_in_failed"
    audit.log("security", action, detail, actor_name=user.username, target=f"user {user.username}")


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_session)):
    """Always works, even if the session has already ended."""
    token = request.cookies.get(sessions.COOKIE_NAME)
    try:
        _, user = sessions.check(db, token)
        audit.log("security", "sign_out", "Signed out", actor=user, target=f"user {user.username}")
    except sessions.SessionEnded:
        pass
    sessions.end(db, token)
    _clear_cookie(request, response)
    return {"ok": True}


@router.get("/me")
def me(current: SignedIn = Depends(current_session)):
    return {"user": user_json(current.user)}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(form: PasswordChange, db: Session = Depends(get_session),
                    current: SignedIn = Depends(current_session)):
    """Also signs out every OTHER session of this user (e.g. on another computer)."""
    try:
        accounts.change_password(db, current.user, form.current_password, form.new_password)
    except AccountError as exc:
        raise HTTPException(400, str(exc))
    sessions.end_all(db, current.user.id, keep=current.session)
    audit.log("security", "password_changed", "Changed their password (other sessions signed out)",
              actor=current.user, target=f"user {current.user.username}")
    return {"user": user_json(current.user)}


class SetupForm(BaseModel):
    username: str
    full_name: str
    password: str


@router.post("/setup", status_code=201)
def setup(form: SetupForm, request: Request, response: Response, db: Session = Depends(get_session)):
    """Only works while there are no users at all. Afterwards: 409. The new Admin is signed in."""
    if not accounts.needs_setup(db):
        raise HTTPException(409, "Setup is already done. Sign in, or ask your Admin for an account.")
    try:
        user = accounts.create_first_admin(db, form.username, form.full_name, form.password)
    except AccountError as exc:
        raise HTTPException(409 if "already done" in str(exc) else 400, str(exc))
    _set_cookie(request, response, sessions.start(db, user))
    audit.log("users", "first_admin", f"First-time setup: made the first Admin account ({user.username}) and signed in",
              actor=user, target=f"user {user.username}")
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
    audit.log("users", "access_requested", f"Asked for a {ROLE_LABELS[request.role]} account ({request.username}): "
                                           f"“{request.reason}”", actor_name=request.full_name,
              target=f"user {request.username}")
    return {"username": request.username, "full_name": request.full_name, "role": request.role,
            "role_label": ROLE_LABELS[request.role], "created_at": request.created_at.isoformat()}


class ForgotForm(BaseModel):
    username: str
    message: str = ""


@router.post("/forgot", status_code=202)
def forgot(form: ForgotForm, db: Session = Depends(get_session)):
    """Always the same answer, so it cannot be used to find out which usernames exist."""
    try:
        request = accounts.request_reset(db, form.username, form.message)
    except AccountError as exc:
        raise HTTPException(400, str(exc))
    user = accounts.find_user(db, form.username)
    if request is not None and user is not None:
        audit.log("users", "reset_requested", "Asked the Admin for a new password (forgot password)",
                  actor_name=user.username, target=f"user {user.username}")
    elif request is not None:
        audit.log("users", "reset_requested", "Forgot-password request for an unknown username", actor_name="Unknown")
    return {"ok": True, "message": "Request sent. Your Admin will check who you are and give you a temporary password."}
