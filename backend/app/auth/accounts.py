"""Accounts: first-time setup, signing in (with lockout), access and reset requests, and the Admin's
changes to users. The routes (app/routes/auth.py and admin.py) only check the form and call these.

Rules:
- No built-in or default accounts. If there are no users yet, the First-time setup screen makes the
  first Admin. After that, setup is closed for good.
- Passwords: at least 12 characters (see passwords.py). 5 wrong passwords in a row lock the account
  for 15 minutes (an Admin can unlock it sooner).
- "Request access" asks an Admin for a new Operator or Reviewer account. Admin accounts are made
  only by an existing Admin.
- "Forgot password" asks an Admin (offline, no email). The Admin sets a temporary password, which
  must be changed at the next sign-in.
- The last active Admin cannot be switched off or made into another role (someone must be able to
  manage users).
"""

import re
import threading
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import (
    PasswordRuleError, check_rules, hash_password, needs_rehash, temporary_password, verify_password,
    waste_time_like_a_check,
)
from app.db import AccountRequest, User, as_utc, utc_now

ROLES = ("operator", "reviewer", "admin")
ROLE_LABELS = {"operator": "Operator", "reviewer": "Reviewer", "admin": "Admin"}
REQUESTABLE_ROLES = ("operator", "reviewer")  # Admin accounts are made only by an Admin

LOCK_AFTER_WRONG = 5
LOCK_MINUTES = 15
MAX_PENDING_REQUESTS = 50  # the sign-in pages are open to anyone; don't let them fill the database

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
_setup_lock = threading.Lock()


class AccountError(ValueError):
    """Something the person can fix; the message is shown to them as it is."""


class SignInError(AccountError):
    """Sign-in refused. `event` says why, for the audit trail:
    unknown_user | wrong_password | locked_now | locked | inactive | pending"""

    def __init__(self, message: str, event: str, user: User | None = None):
        super().__init__(message)
        self.event = event
        self.user = user


def clean_username(raw: str) -> str:
    username = (raw or "").strip().lower()
    if not _USERNAME.match(username):
        raise AccountError("The username must be 3 to 40 characters: letters, numbers, dot, dash or underscore "
                           "(for example priya.sharma or EMP-20311).")
    return username


def clean_name(raw: str) -> str:
    name = " ".join((raw or "").split())
    if not 2 <= len(name) <= 100:
        raise AccountError("Please enter the full name (2 to 100 characters).")
    return name


def _check_password(password: str, username: str, full_name: str) -> None:
    try:
        check_rules(password, username, full_name)
    except PasswordRuleError as exc:
        raise AccountError(str(exc)) from exc


def _check_role(role: str, allowed=ROLES) -> str:
    role = (role or "").strip().lower()
    if role not in allowed:
        raise AccountError(f"The role must be one of: {', '.join(ROLE_LABELS[r] for r in allowed)}.")
    return role


def find_user(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == (username or "").strip().lower()))


def _username_taken(db: Session, username: str) -> bool:
    if find_user(db, username) is not None:
        return True
    return db.scalar(select(AccountRequest.id).where(
        AccountRequest.kind == "access", AccountRequest.status == "pending", AccountRequest.username == username,
    )) is not None


# ---- first-time setup ------------------------------------------------------------------------


def needs_setup(db: Session) -> bool:
    """True until the first account exists."""
    return db.scalar(select(func.count(User.id))) == 0


def create_first_admin(db: Session, username: str, full_name: str, password: str) -> User:
    username, full_name = clean_username(username), clean_name(full_name)
    _check_password(password, username, full_name)
    with _setup_lock:  # two setup forms sent at the same moment must not both succeed
        if not needs_setup(db):
            raise AccountError("Setup is already done. Sign in, or ask your Admin for an account.")
        user = User(username=username, full_name=full_name, role="admin", password_hash=hash_password(password))
        db.add(user)
        db.commit()
    return user


# ---- signing in ------------------------------------------------------------------------------


def is_locked(user: User, now: datetime | None = None) -> bool:
    locked_until = as_utc(user.locked_until)
    return locked_until is not None and locked_until > (now or utc_now())


def sign_in(db: Session, username: str, password: str) -> User:
    """Check the username and password. Returns the user, or raises SignInError (already saved:
    wrong-password counts and locks are committed)."""
    wrong = "Wrong username or password."
    user = find_user(db, username)
    if user is None:
        waste_time_like_a_check(password)
        pending = db.scalar(select(AccountRequest).where(
            AccountRequest.kind == "access", AccountRequest.status == "pending",
            AccountRequest.username == (username or "").strip().lower(),
        ))
        if pending is not None and pending.password_hash and verify_password(pending.password_hash, password):
            raise SignInError("Your access request is still waiting for an Admin to approve it.", "pending")
        raise SignInError(wrong, "unknown_user")

    now = utc_now()
    if is_locked(user, now):
        raise SignInError(_locked_message(user), "locked", user)

    if not verify_password(user.password_hash, password):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= LOCK_AFTER_WRONG:
            user.failed_attempts = 0
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            db.commit()
            raise SignInError(_locked_message(user), "locked_now", user)
        db.commit()
        left = LOCK_AFTER_WRONG - user.failed_attempts
        hint = f" {left} {'try' if left == 1 else 'tries'} left before the account is locked." if left <= 2 else ""
        raise SignInError(wrong + hint, "wrong_password", user)

    if not user.is_active:
        raise SignInError("This account is switched off. Ask your Admin.", "inactive", user)

    user.failed_attempts, user.locked_until, user.last_login = 0, None, now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    db.commit()
    return user


def _locked_message(user: User) -> str:
    return (f"This account is locked for {LOCK_MINUTES} minutes after {LOCK_AFTER_WRONG} wrong passwords. "
            "Try again later, or ask your Admin to unlock it.")


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(user.password_hash, current):
        raise AccountError("The current password is wrong.")
    if current == new:
        raise AccountError("The new password must be different from the current one.")
    _check_password(new, user.username, user.full_name)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    db.commit()


# ---- requests from the sign-in pages ------------------------------------------------------------


def _too_many_pending(db: Session) -> bool:
    count = db.scalar(select(func.count(AccountRequest.id)).where(AccountRequest.status == "pending"))
    return count >= MAX_PENDING_REQUESTS


def request_access(db: Session, username: str, full_name: str, role: str, reason: str, password: str) -> AccountRequest:
    username, full_name = clean_username(username), clean_name(full_name)
    role = _check_role(role, REQUESTABLE_ROLES)
    reason = " ".join((reason or "").split())[:500]
    if len(reason) < 5:
        raise AccountError("Please say in a few words why you need access.")
    _check_password(password, username, full_name)
    if _username_taken(db, username):
        raise AccountError("This username is already used. Choose another one.")
    if _too_many_pending(db):
        raise AccountError("Too many requests are waiting. Please ask your Admin in person.")
    request = AccountRequest(kind="access", username=username, full_name=full_name, role=role, reason=reason,
                             password_hash=hash_password(password))
    db.add(request)
    db.commit()
    return request


def request_reset(db: Session, username: str, message: str) -> AccountRequest | None:
    """"Forgot password". The answer never says whether the username exists; a second request for the
    same username while one is waiting is not stored again."""
    username = (username or "").strip().lower()[:40]
    if not username:
        raise AccountError("Please enter your username.")
    already = db.scalar(select(AccountRequest).where(
        AccountRequest.kind == "reset", AccountRequest.status == "pending", AccountRequest.username == username,
    ))
    if already is not None or _too_many_pending(db):
        return already
    request = AccountRequest(kind="reset", username=username, reason=" ".join((message or "").split())[:500])
    db.add(request)
    db.commit()
    return request


# ---- the Admin's changes ------------------------------------------------------------------------


def approve_access(db: Session, request: AccountRequest, admin: User, role: str | None = None) -> User:
    if request.kind != "access" or request.status != "pending":
        raise AccountError("This request has already been handled.")
    if find_user(db, request.username) is not None:
        raise AccountError("A user with this username already exists. Reject this request.")
    user = User(username=request.username, full_name=request.full_name,
                role=_check_role(role or request.role or "", REQUESTABLE_ROLES),
                password_hash=request.password_hash)
    db.add(user)
    request.status, request.decided_at, request.decided_by = "approved", utc_now(), admin.id
    request.password_hash = None  # now kept on the user only
    db.commit()
    return user


def reject_request(db: Session, request: AccountRequest, admin: User) -> None:
    if request.status != "pending":
        raise AccountError("This request has already been handled.")
    request.status, request.decided_at, request.decided_by = "rejected", utc_now(), admin.id
    request.password_hash = None
    db.commit()


def create_user(db: Session, admin: User, username: str, full_name: str, role: str) -> tuple[User, str]:
    """A new account with a temporary password (shown once to the Admin; changed at first sign-in)."""
    username, full_name, role = clean_username(username), clean_name(full_name), _check_role(role)
    if _username_taken(db, username):
        raise AccountError("This username is already used (or waiting in an access request).")
    password = temporary_password()
    user = User(username=username, full_name=full_name, role=role, password_hash=hash_password(password),
                must_change_password=True)
    db.add(user)
    db.commit()
    return user, password


def _active_admins(db: Session) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True)))


def update_user(db: Session, admin: User, user: User, *, full_name: str | None = None, role: str | None = None,
                is_active: bool | None = None, unlock: bool = False) -> list[str]:
    """Change a user. Returns what changed, in plain words (for the audit trail)."""
    changes: list[str] = []
    role = _check_role(role) if role is not None else None
    if full_name is not None and clean_name(full_name) != user.full_name:
        changes.append(f"name {user.full_name} → {clean_name(full_name)}")
        user.full_name = clean_name(full_name)
    removing_admin = (user.role == "admin" and user.is_active
                      and ((role is not None and role != "admin") or is_active is False))
    if removing_admin and _active_admins(db) <= 1:
        raise AccountError("This is the only active Admin. Make another Admin first.")
    if role is not None and role != user.role:
        changes.append(f"role {ROLE_LABELS[user.role]} → {ROLE_LABELS[role]}")
        user.role = role
    if is_active is not None and is_active != user.is_active:
        if user.id == admin.id and not is_active:
            raise AccountError("You cannot switch off your own account.")
        changes.append("switched on" if is_active else "switched off")
        user.is_active = is_active
    if unlock and (is_locked(user) or user.failed_attempts):
        changes.append("unlocked")
        user.locked_until, user.failed_attempts = None, 0
    db.commit()
    return changes


def reset_password(db: Session, admin: User, user: User) -> str:
    """Set a temporary password (shown once to the Admin). Also unlocks the account and closes any
    waiting "Forgot password" request for this user."""
    password = temporary_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.locked_until, user.failed_attempts = None, 0
    for request in db.scalars(select(AccountRequest).where(
        AccountRequest.kind == "reset", AccountRequest.status == "pending", AccountRequest.username == user.username,
    )):
        request.status, request.decided_at, request.decided_by = "done", utc_now(), admin.id
    db.commit()
    return password
