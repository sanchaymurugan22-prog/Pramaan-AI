"""Notification routes (Stage 9A). Everyone sees only their own notifications.

GET  /api/notifications              {"items": [...newest first], "unread": 3}   ?unread=true for unread only
GET  /api/notifications/count        {"unread": 3}   (the bell polls this)
POST /api/notifications/{id}/read    mark one as read
POST /api/notifications/read-all     mark all of mine as read
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.deps import signed_in
from app.db import Notification, User, as_utc, get_session, utc_now

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _unread(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Notification)
                     .where(Notification.user_id == user.id, Notification.read_at.is_(None))) or 0


def _json(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "detail": n.detail, "job_id": n.job_id,
            "created_at": as_utc(n.created_at).isoformat(), "read": n.read_at is not None}


@router.get("")
def list_notifications(unread: bool = False, db: Session = Depends(get_session), user: User = Depends(signed_in)):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread:
        query = query.where(Notification.read_at.is_(None))
    items = db.scalars(query.order_by(Notification.id.desc()).limit(100))
    return {"items": [_json(n) for n in items], "unread": _unread(db, user)}


@router.get("/count")
def count(db: Session = Depends(get_session), user: User = Depends(signed_in)):
    return {"unread": _unread(db, user)}


@router.post("/read-all")
def read_all(db: Session = Depends(get_session), user: User = Depends(signed_in)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
               .values(read_at=utc_now()))
    db.commit()
    return {"unread": 0}


@router.post("/{notification_id}/read")
def read_one(notification_id: int, db: Session = Depends(get_session), user: User = Depends(signed_in)):
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:  # someone else's: same answer as "does not exist"
        raise HTTPException(404, "Notification not found.")
    if note.read_at is None:
        note.read_at = utc_now()
        db.commit()
    return {"unread": _unread(db, user)}
