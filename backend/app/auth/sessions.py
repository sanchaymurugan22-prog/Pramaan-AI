"""Sign-in sessions, kept on the server (table `sessions`).

- Signing in makes a random 256-bit token. The browser keeps it in a cookie the page's JavaScript
  cannot read (HttpOnly) and that other websites cannot make the browser send (SameSite=Strict).
- The database keeps only an HMAC-SHA256 fingerprint of the token (keyed with APP_SECRET_KEY), so
  someone with a copy of the database still cannot sign in.
- A session ends 8 hours after signing in, or after 30 minutes without any request, whichever comes
  first. Signing out deletes it. Switching a user off or setting a new password ends all their sessions.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.db import User, UserSession, as_utc, utc_now

COOKIE_NAME = "pramaan_session"
MAX_AGE = timedelta(hours=8)
IDLE_LIMIT = timedelta(minutes=30)
# last_seen is saved at most this often (not on every request, e.g. while a page is polling)
TOUCH_EVERY = timedelta(seconds=60)


@dataclass
class SessionEnded(Exception):
    """The cookie is missing, unknown or too old. `reason`: missing | unknown | expired | idle | inactive"""

    reason: str
    user: User | None = None

    @property
    def message(self) -> str:
        return {
            "expired": "Your session has ended (8-hour limit). Please sign in again.",
            "idle": "You were signed out after 30 minutes without activity. Please sign in again.",
            "inactive": "This account is switched off. Ask your Admin.",
        }.get(self.reason, "Please sign in.")


def _fingerprint(token: str) -> str:
    return hmac.new(settings.app_secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def start(db: Session, user: User) -> str:
    """Make a new session for the user. Returns the token for the cookie (not stored anywhere else)."""
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=_fingerprint(token), user_id=user.id))
    db.commit()
    return token


def check(db: Session, token: str | None) -> tuple[UserSession, User]:
    """The session and user for a cookie value, or SessionEnded. Ended sessions are deleted."""
    if not token:
        raise SessionEnded("missing")
    row = db.scalar(select(UserSession).where(UserSession.token_hash == _fingerprint(token)))
    if row is None:
        raise SessionEnded("unknown")
    now = utc_now()
    user = row.user
    reason = None
    if now - as_utc(row.created_at) > MAX_AGE:
        reason = "expired"
    elif now - as_utc(row.last_seen) > IDLE_LIMIT:
        reason = "idle"
    elif user is None or not user.is_active:
        reason = "inactive"
    if reason:
        db.delete(row)
        db.commit()
        if user is not None:
            audit.log("security", "session_ended", SessionEnded(reason).message.split(".")[0],
                      actor=user, target=f"user {user.username}")
        raise SessionEnded(reason, user)
    if now - as_utc(row.last_seen) > TOUCH_EVERY:
        row.last_seen = now
        db.commit()
    return row, user


def end(db: Session, token: str | None) -> None:
    """Sign out: delete this session (nothing happens if it is already gone)."""
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _fingerprint(token)))
        db.commit()


def end_all(db: Session, user_id: int, keep: UserSession | None = None) -> None:
    """End every session of a user (e.g. after a password reset), except `keep` if given."""
    query = delete(UserSession).where(UserSession.user_id == user_id)
    if keep is not None:
        query = query.where(UserSession.id != keep.id)
    db.execute(query)
    db.commit()
