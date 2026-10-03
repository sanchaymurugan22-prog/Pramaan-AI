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
import secrets
import sys
import threading
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import (
    PasswordRuleError, check_rules, hash_password, needs_rehash, temporary_password, verify_password,
    waste_time_like_a_check,
)
from app.lang import languages
from app.db import AccountRequest, User, as_utc, utc_now

ROLES = ("operator", "reviewer", "admin")
ROLE_LABELS = {"operator": "Operator", "reviewer": "Reviewer", "admin": "Admin"}
REQUESTABLE_ROLES = ("operator", "reviewer")  # Admin accounts are made only by an Admin

LOCK_AFTER_WRONG = 5  # the default; an Admin can choose 3, 5 or 10 (Security & policies, Stage 9B)
LOCK_MINUTES = 15
MAX_PENDING_REQUESTS = 50  # the sign-in pages are open to anyone; don't let them fill the database

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,29}$")
_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")

# Stage 9B: the divisions offered in the forms (anything else can be typed by an Admin), and the 23
# languages of the language screen.
DIVISIONS = ["Cyber operations", "Public communication", "Research and analysis", "Administration", "Other"]
LANGUAGES = {code: lang.native for code, lang in languages.LANGUAGES.items()}  # Stage 8: app/lang/languages.py
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


def clean_employee_id(raw: str | None) -> str | None:
    """"emp-20417 " -> "EMP-20417"; empty -> None."""
    value = (raw or "").strip().upper()
    if not value:
        return None
    if not _EMPLOYEE_ID.match(value):
        raise AccountError("The employee ID may have letters, numbers and dashes only (for example EMP-20417).")
    return value


def clean_email(raw: str | None) -> str | None:
    value = (raw or "").strip().lower()
    if not value:
        return None
    if len(value) > 120 or not _EMAIL.match(value):
        raise AccountError("Please enter a valid official email address (for example name@org.gov.in).")
    return value


def clean_division(raw: str | None) -> str:
    return " ".join((raw or "").split())[:80]


def clean_language(raw: str | None) -> str:
    value = (raw or "en").strip().lower()
    if value not in LANGUAGES:
        raise AccountError("Choose a language from the list.")
    return value


def find_user(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == (username or "").strip().lower()))


def find_for_sign_in(db: Session, typed: str) -> User | None:
    """The account for what was typed in the sign-in box: a username, an employee ID or an email."""
    typed = (typed or "").strip()
    if not typed:
        return None
    return (find_user(db, typed)
            or db.scalar(select(User).where(User.employee_id == typed.upper()))
            or db.scalar(select(User).where(User.email == typed.lower())))


def _detail_taken(db: Session, employee_id: str | None, email: str | None, except_user: int | None = None) -> str | None:
    """Is this employee ID or email already used by another account or a waiting request?"""
    for field, value, words in ((User.employee_id, employee_id, "employee ID"), (User.email, email, "email")):
        if value is None:
            continue
        other = db.scalar(select(User).where(field == value))
        if other is not None and other.id != except_user:
            return f"This {words} is already used by another account."
        request_field = AccountRequest.employee_id if words == "employee ID" else AccountRequest.email
        if except_user is None and db.scalar(select(AccountRequest.id).where(
                AccountRequest.kind == "access", AccountRequest.status == "pending", request_field == value)):
            return f"This {words} is already in a waiting access request."
    return None


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


def seed_demo_accounts(db: Session) -> None:
    """Ensure SIH Judge demo accounts exist for easy evaluation."""
    judge = find_user(db, "sih.judge")
    if not judge:
        judge = User(
            username="sih.judge",
            full_name="SIH Evaluation Judge",
            role="operator",
            password_hash=hash_password("JudgePassword123!"),
            employee_id="SIH-2026-JUDGE",
            email="judge@sih.gov.in",
            division="Cyber operations",
            created_at=utc_now(),
        )
        db.add(judge)
    else:
        judge.role = "operator"

    reviewer = find_user(db, "reviewer.demo")
    if not reviewer:
        reviewer = User(
            username="reviewer.demo",
            full_name="Demo Reviewer",
            role="reviewer",
            password_hash=hash_password("ReviewerPassword123!"),
            employee_id="REV-2026-DEMO",
            email="reviewer@sih.gov.in",
            division="Cyber operations",
            created_at=utc_now(),
        )
        db.add(reviewer)
    else:
        reviewer.role = "reviewer"

    admin_user = find_user(db, "admin.demo")
    if not admin_user:
        admin_user = User(
            username="admin.demo",
            full_name="Demo Administrator",
            role="admin",
            password_hash=hash_password("AdminPassword123!"),
            employee_id="ADM-2026-DEMO",
            email="admin@sih.gov.in",
            division="Administration",
            created_at=utc_now(),
        )
        db.add(admin_user)
    else:
        admin_user.role = "admin"

    db.commit()




# v1.2: the one-time setup code. Without it, anyone who could open the page before the installer did (for
# example on the office network) could make themselves the first Admin. The server prints the code in ITS
# terminal (the window where scripts/start.sh runs), which only the person who installed it can see. It is
# kept in memory only (never in a file, the database, the logs or the audit trail), used once, and replaced
# after SETUP_TRIES wrong tries, so it cannot be guessed.
SETUP_TRIES = 5
_CODE_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L: easy to read and type
_code_lock = threading.Lock()
_setup_code: str | None = None
_wrong_codes = 0


def setup_code(new: bool = False) -> str:
    """The current setup code, e.g. "K7P4-M9QX" (made and printed in the terminal when first needed)."""
    global _setup_code, _wrong_codes
    with _code_lock:
        if _setup_code is None or new:
            _setup_code = "-".join("".join(secrets.choice(_CODE_LETTERS) for _ in range(4)) for _ in range(2))
            _wrong_codes = 0
            _print_setup_code(_setup_code)
        return _setup_code


def _print_setup_code(code: str) -> None:
    line = "=" * 64
    print(f"\n{line}\n  Pramaan AI - First-time setup\n\n  Setup code:  {code}\n\n"
          "  Type this code on the First-time setup page to create the first Admin.\n"
          "  It works once. A new code is printed here after 5 wrong tries or a restart.\n"
          f"{line}\n", file=sys.stderr, flush=True)  # the terminal (not the log files)


def _check_setup_code(typed: str) -> None:
    """Raises AccountError if the code is wrong (after SETUP_TRIES wrong tries, a new code is printed)."""
    global _wrong_codes
    expected = setup_code()
    cleaned = re.sub(r"[\s-]", "", typed or "").upper()
    if secrets.compare_digest(cleaned.encode(), expected.replace("-", "").encode()):
        return
    with _code_lock:
        _wrong_codes += 1
        too_many = _wrong_codes >= SETUP_TRIES
    if too_many:
        setup_code(new=True)
        raise AccountError("Wrong setup code, too many times. A NEW code is now printed in the terminal where "
                           "Pramaan AI was started.")
    raise AccountError("Wrong setup code. It is printed in the terminal (the window where Pramaan AI was "
                       "started, for example by scripts/start.sh).")


def create_first_admin(db: Session, username: str, full_name: str, password: str,
                       employee_id: str | None = None, email: str | None = None, code: str = "") -> User:
    global _setup_code
    if not needs_setup(db):
        raise AccountError("Setup is already done. Sign in, or ask your Admin for an account.")
    _check_setup_code(code)
    employee_id, email = clean_employee_id(employee_id), clean_email(email)
    if not (username or "").strip() and employee_id is None:
        raise AccountError("Enter a username or an employee ID.")
    username, full_name = clean_username(username or (employee_id or "").lower()), clean_name(full_name)
    _check_password(password, username, full_name)
    with _setup_lock:  # two setup forms sent at the same moment must not both succeed
        if not needs_setup(db):
            raise AccountError("Setup is already done. Sign in, or ask your Admin for an account.")
        user = User(username=username, full_name=full_name, role="admin", password_hash=hash_password(password),
                    last_login=utc_now(), employee_id=employee_id, email=email,
                    division="Administration")  # setup signs the new Admin in
        db.add(user)
        db.commit()
    with _code_lock:
        _setup_code = None  # used: it never works again
    return user


# ---- signing in ------------------------------------------------------------------------------


def lock_after() -> int:
    """Wrong passwords in a row before an account is locked (the Admin's security policy)."""
    from app.app_settings import lock_after as policy_lock_after  # here: app_settings needs the database set up
    return policy_lock_after()


def is_locked(user: User, now: datetime | None = None) -> bool:
    locked_until = as_utc(user.locked_until)
    return locked_until is not None and locked_until > (now or utc_now())


def sign_in(db: Session, username: str, password: str) -> User:
    """Check the username and password. Returns the user, or raises SignInError (already saved:
    wrong-password counts and locks are committed)."""
    wrong = "Wrong username or password."
    user = find_for_sign_in(db, username)
    if user is None:
        waste_time_like_a_check(password)
        typed = (username or "").strip()
        pending = db.scalar(select(AccountRequest).where(
            AccountRequest.kind == "access", AccountRequest.status == "pending",
            (AccountRequest.username == typed.lower()) | (AccountRequest.employee_id == typed.upper())
            | (AccountRequest.email == typed.lower()),
        ))
        if pending is not None and pending.password_hash and verify_password(pending.password_hash, password):
            raise SignInError("Your access request is still waiting for an Admin to approve it.", "pending")
        raise SignInError(wrong, "unknown_user")

    now = utc_now()
    if is_locked(user, now):
        raise SignInError(_locked_message(user), "locked", user)

    if not verify_password(user.password_hash, password):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= lock_after():
            user.failed_attempts = 0
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            db.commit()
            raise SignInError(_locked_message(user), "locked_now", user)
        db.commit()
        left = lock_after() - user.failed_attempts
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
    return (f"This account is locked for {LOCK_MINUTES} minutes after {lock_after()} wrong passwords. "
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


def request_access(db: Session, username: str, full_name: str, role: str, reason: str, password: str,
                   employee_id: str | None = None, email: str | None = None, division: str = "",
                   language: str = "en") -> AccountRequest:
    """Stage 9B: the username may be left out; then the employee ID (lower case) is the username."""
    employee_id, email = clean_employee_id(employee_id), clean_email(email)
    if not (username or "").strip() and employee_id is None:
        raise AccountError("Please enter your employee ID.")
    username = clean_username(username or (employee_id or "").lower())
    full_name = clean_name(full_name)
    role = _check_role(role, REQUESTABLE_ROLES)
    reason = " ".join((reason or "").split())[:500]
    _check_password(password, username, full_name)
    taken = _detail_taken(db, employee_id, email)
    if taken:
        raise AccountError(taken)
    if _username_taken(db, username):
        raise AccountError("This username is already used. Choose another one.")
    if _too_many_pending(db):
        raise AccountError("Too many requests are waiting. Please ask your Admin in person.")
    request = AccountRequest(kind="access", username=username, full_name=full_name, role=role, reason=reason,
                             password_hash=hash_password(password), employee_id=employee_id, email=email,
                             division=clean_division(division), language=clean_language(language))
    db.add(request)
    db.commit()
    return request


def request_reset(db: Session, username: str, message: str) -> AccountRequest | None:
    """"Forgot password". The answer never says whether the username exists; a second request for the
    same username while one is waiting is not stored again."""
    typed = (username or "").strip()[:120]
    if not typed:
        raise AccountError("Please enter your username or employee ID.")
    user = find_for_sign_in(db, typed)
    username = user.username if user is not None else typed.lower()[:40]
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
    for field, value in ((User.employee_id, request.employee_id), (User.email, request.email)):
        if value is not None and db.scalar(select(User.id).where(field == value)) is not None:
            raise AccountError("Another account already has this employee ID or email. Reject this request.")
    user = User(username=request.username, full_name=request.full_name,
                role=_check_role(role or request.role or "", REQUESTABLE_ROLES),
                password_hash=request.password_hash, employee_id=request.employee_id, email=request.email,
                division=request.division or "", language=request.language or "en")
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


def create_user(db: Session, admin: User, username: str, full_name: str, role: str, *,
                employee_id: str | None = None, email: str | None = None, division: str = "",
                dsc_holder: bool = False, emergency_duty: bool = False) -> tuple[User, str]:
    """A new account with a temporary password (shown once to the Admin; changed at first sign-in).
    Stage 9B: the username may be left out; then the employee ID (lower case) is the username."""
    employee_id, email = clean_employee_id(employee_id), clean_email(email)
    if not (username or "").strip() and employee_id is None:
        raise AccountError("Enter a username or an employee ID.")
    username = clean_username(username or (employee_id or "").lower())
    full_name, role = clean_name(full_name), _check_role(role)
    taken = _detail_taken(db, employee_id, email)
    if taken:
        raise AccountError(taken)
    if _username_taken(db, username):
        raise AccountError("This username is already used (or waiting in an access request).")
    password = temporary_password()
    user = User(username=username, full_name=full_name, role=role, password_hash=hash_password(password),
                must_change_password=True, employee_id=employee_id, email=email, division=clean_division(division),
                dsc_holder=dsc_holder and role == "reviewer", emergency_duty=emergency_duty)
    db.add(user)
    db.commit()
    return user, password


def _active_admins(db: Session) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True)))


def update_user(db: Session, admin: User, user: User, *, full_name: str | None = None, role: str | None = None,
                is_active: bool | None = None, unlock: bool = False, employee_id: str | None = None,
                email: str | None = None, division: str | None = None, dsc_holder: bool | None = None,
                emergency_duty: bool | None = None) -> list[str]:
    """Change a user. Returns what changed, in plain words (for the audit trail).
    employee_id / email: None = unchanged, "" = remove."""
    changes: list[str] = []
    new_id = clean_employee_id(employee_id) if employee_id is not None else user.employee_id
    new_email = clean_email(email) if email is not None else user.email
    taken = _detail_taken(db, new_id if new_id != user.employee_id else None,
                          new_email if new_email != user.email else None, except_user=user.id)
    if taken:
        raise AccountError(taken)
    for label, attr, value in (("employee ID", "employee_id", new_id), ("email", "email", new_email),
                               ("division", "division", clean_division(division) if division is not None else user.division)):
        if value != getattr(user, attr):
            changes.append(f"{label} {getattr(user, attr) or '—'} → {value or '—'}")
            setattr(user, attr, value)
    for label, attr, value in (("DSC token holder", "dsc_holder", dsc_holder), ("emergency duty", "emergency_duty", emergency_duty)):
        if value is not None and value != getattr(user, attr):
            changes.append(f"{label} {'on' if value else 'off'}")
            setattr(user, attr, value)
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
