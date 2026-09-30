"""Who is asking? FastAPI dependencies that every protected route uses.

    user: User = Depends(allow("operator"))              only Operators
    user: User = Depends(allow("operator", "reviewer"))  Operators and Reviewers
    user: User = Depends(signed_in)                       anyone signed in

401 = not signed in (or the session has ended), 403 = signed in, but this role may not do it.
Roles are checked HERE, in the backend, on every request. Hiding a button in the web page is only
for convenience; it protects nothing.

Someone who signed in with a temporary password may only change it (or sign out) until they have.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import sessions
from app.auth.accounts import ROLE_LABELS
from app.db import User, UserSession, get_session


@dataclass
class SignedIn:
    user: User
    session: UserSession


def current_session(request: Request, db: Session = Depends(get_session)) -> SignedIn:
    """The signed-in user and session, even while the password is a temporary one."""
    try:
        row, user = sessions.check(db, request.cookies.get(sessions.COOKIE_NAME))
    except sessions.SessionEnded as ended:
        raise HTTPException(401, ended.message)
    request.state.user = user
    return SignedIn(user, row)


def signed_in(current: SignedIn = Depends(current_session)) -> User:
    """Anyone signed in, who has chosen their own password."""
    if current.user.must_change_password:
        raise HTTPException(403, "Choose a new password first (you signed in with a temporary one).")
    return current.user


def allow(*roles: str):
    """A dependency that lets only these roles through."""
    names = " and ".join(f"{ROLE_LABELS[r]}s" for r in roles)

    def check(user: User = Depends(signed_in)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Only {names} can do this. You are signed in as {ROLE_LABELS[user.role]}.")
        return user

    check.allowed_roles = roles  # read by the permission tests
    return check
