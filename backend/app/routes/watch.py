"""Watch folder routes (Stage 9A, Operators only). See app/watch.py for how the folder is checked.

GET  /api/watch            my settings, the folders I can pick (inside data/watch/), recent activity
PUT  /api/watch            {"enabled", "folder", "outputs", "skip_duplicates", "notify"} (only the ones sent change)
POST /api/watch/folders    {"name": "incoming"} make a new folder inside data/watch/
POST /api/watch/check      check my folder now, instead of waiting for the next minute
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import watch
from app.auth.deps import allow
from app.config import settings
from app.db import Job, User, WatchFile, as_utc, get_session
from app.pipeline.output_types import OUTPUT_TYPES

router = APIRouter(prefix="/api/watch", tags=["watch"])
OPERATOR = allow("operator")


def _state(db: Session, user: User) -> dict:
    row = watch.settings_for(db, user)
    db.commit()
    items = db.scalars(select(WatchFile).where(WatchFile.user_id == user.id).order_by(WatchFile.id.desc()).limit(30))
    return {
        "enabled": row.enabled,
        "folder": row.folder,
        "outputs": row.outputs,
        "skip_duplicates": row.skip_duplicates,
        "notify": row.notify,
        "last_check": as_utc(row.last_check).isoformat() if row.last_check else None,
        "interval_seconds": settings.watch_interval_seconds,
        "root": str(watch.WATCH_ROOT),
        "folders": watch.list_folders(),
        "activity": [watch.activity_json(item, db.get(Job, item.job_id) if item.job_id else None) for item in items],
    }


@router.get("")
def get_watch(db: Session = Depends(get_session), user: User = Depends(OPERATOR)):
    return _state(db, user)


class WatchUpdate(BaseModel):
    enabled: bool | None = None
    folder: str | None = None
    outputs: list[str] | None = None
    skip_duplicates: bool | None = None
    notify: bool | None = None


@router.put("")
def update_watch(body: WatchUpdate, db: Session = Depends(get_session), user: User = Depends(OPERATOR)):
    row = watch.settings_for(db, user)
    if body.folder is not None:
        try:
            path = watch.folder_path(body.folder)
        except watch.WatchError as exc:
            raise HTTPException(400, str(exc))
        if not path.is_dir():
            raise HTTPException(400, f"There is no folder data/watch/{body.folder.strip()}. Make it first.")
        row.folder = body.folder.strip().rstrip("/")
    if body.outputs is not None:
        unknown = [o for o in body.outputs if o not in OUTPUT_TYPES]
        if unknown or not body.outputs:
            raise HTTPException(400, "Choose at least one known output for the kit.")
        row.outputs = list(dict.fromkeys(body.outputs))
    for name in ("enabled", "skip_duplicates", "notify"):
        value = getattr(body, name)
        if value is not None:
            setattr(row, name, value)
    db.commit()
    watch.audit_settings_change(user, row)
    return _state(db, user)


class NewFolder(BaseModel):
    name: str


@router.post("/folders")
def new_folder(body: NewFolder, db: Session = Depends(get_session), user: User = Depends(OPERATOR)):
    try:
        name = watch.make_folder(body.name)
    except watch.WatchError as exc:
        raise HTTPException(400, str(exc))
    return {"folder": name, "folders": watch.list_folders()}


@router.post("/check")
def check_now(db: Session = Depends(get_session), user: User = Depends(OPERATOR)):
    row = watch.settings_for(db, user)
    if not row.enabled:
        raise HTTPException(409, "Switch the watch folder on first.")
    handled = watch.check(db, row)
    return _state(db, user) | {"new": len(handled)}
