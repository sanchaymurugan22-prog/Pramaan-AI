"""Watch folder (Stage 9A): new reports dropped in a folder become DRAFT jobs automatically.

Each Operator may switch on one folder inside data/watch/ (for example data/watch/incoming). Every
minute (WATCH_INTERVAL_SECONDS) the folder is checked; each new .txt, .pdf or .docx file is read and
safety-scanned exactly like an upload on "New transformation", and saved as a draft job owned by that
Operator. The job then WAITS at the Safety check: no AI ever runs until a person has checked it, chosen
the sharing label and pressed Generate. (Watch jobs are drafts; the runner never runs drafts.)

Rules:
  - Only folders inside data/watch/ can be watched (a folder name like "../secrets" is refused).
  - A file still being copied (changed in the last few seconds) waits for the next check.
  - Every file is handled once: it is remembered by name, size and time (watch_files table).
  - "Skip duplicates": a file whose SHA-256 matches a source of an earlier job is skipped ("same as job #0139").
  - Files of other types are listed once as skipped. Pramaan never moves, changes or deletes your files;
    the copy inside Pramaan is encrypted like every other source.
"""

import hashlib
import logging
import re
import threading
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, notifications
from app.config import settings
from app.db import Job, SessionLocal, Source, User, WatchFile, WatchSettings, as_utc, utc_now
from app.pipeline import ingest
from app.pipeline.output_types import OUTPUT_TYPES
from app.routes.jobs import log_created, save_draft

log = logging.getLogger("pramaan.watch")

WATCH_ROOT = settings.data_dir / "watch"
DEFAULT_FOLDER = "incoming"
DEFAULT_OUTPUTS = ["advisory", "executive_summary", "presentation"]  # "Cyber advisory kit"
STABLE_SECONDS = 3  # a file changed more recently than this may still be copying
FOLDER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,59}$")

_lock = threading.Lock()  # one check at a time (the timer and the "Check now" button)


class WatchError(Exception):
    """A folder name that is not allowed."""


def folder_path(name: str) -> Path:
    """data/watch/<name>, refusing anything that would point outside data/watch/."""
    name = (name or "").strip().rstrip("/")
    if not name:
        raise WatchError("Choose a folder.")
    if name.startswith(("/", "\\", "~")):
        raise WatchError("Give the folder's name inside data/watch/, not a full path.")
    parts = name.split("/")
    if len(parts) > 2 or not all(FOLDER_NAME.match(p) and p not in (".", "..") for p in parts):
        raise WatchError("Use a simple folder name inside data/watch/: letters, numbers, spaces, - and _.")
    path = (WATCH_ROOT / name).resolve()
    if not path.is_relative_to(WATCH_ROOT.resolve()):
        raise WatchError("The watch folder must be inside data/watch/.")
    return path


def list_folders() -> list[str]:
    """The folders that can be watched: every folder in data/watch/ (and one level below it)."""
    WATCH_ROOT.mkdir(parents=True, exist_ok=True)
    (WATCH_ROOT / DEFAULT_FOLDER).mkdir(exist_ok=True)
    found = []
    for path in sorted(WATCH_ROOT.iterdir()):
        if path.is_dir() and not path.name.startswith("."):
            found.append(path.name)
            found += [f"{path.name}/{sub.name}" for sub in sorted(path.iterdir())
                      if sub.is_dir() and not sub.name.startswith(".")]
    return found


def make_folder(name: str) -> str:
    path = folder_path(name)
    path.mkdir(parents=True, exist_ok=True)
    return path.relative_to(WATCH_ROOT.resolve()).as_posix()


def settings_for(db: Session, user: User) -> WatchSettings:
    """This Operator's watch settings (made with the defaults the first time)."""
    row = db.get(WatchSettings, user.id)
    if row is None:
        row = WatchSettings(user_id=user.id, enabled=False, folder=DEFAULT_FOLDER, outputs=list(DEFAULT_OUTPUTS),
                            skip_duplicates=True, notify=True)
        db.add(row)
        db.flush()
    return row


def check(db: Session, row: WatchSettings, now: float | None = None) -> list[WatchFile]:
    """Look once for new files in this Operator's folder. Returns what was done with each new file."""
    with _lock:
        return _check(db, row, time.time() if now is None else now)


def _check(db: Session, row: WatchSettings, now: float) -> list[WatchFile]:
    owner = db.get(User, row.user_id)
    if owner is None or not owner.is_active or owner.role != "operator":
        return []
    try:
        folder = folder_path(row.folder)
    except WatchError:
        return []
    row.last_check = utc_now()
    if not folder.is_dir():
        db.commit()
        return []

    seen = {(f.filename, f.size, f.mtime) for f in db.scalars(
        select(WatchFile).where(WatchFile.user_id == row.user_id, WatchFile.folder == row.folder))}
    handled: list[WatchFile] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name.startswith((".", "~$")):
            continue  # hidden files and Word's lock files
        info = path.stat()
        key = (path.name, info.st_size, info.st_mtime)
        if key in seen or now - info.st_mtime < STABLE_SECONDS:
            continue  # done before, or still being copied
        handled.append(_handle(db, row, owner, path, info))
    db.commit()

    for item in handled:
        if item.status == "drafted":
            log_created(db.get(Job, item.job_id), owner, how=" (found by the watch folder)")
    return handled


def _handle(db: Session, row: WatchSettings, owner: User, path: Path, info) -> WatchFile:
    """Make a draft job from one new file (or say why not). Adds rows; the caller commits."""
    item = WatchFile(user_id=row.user_id, folder=row.folder, filename=path.name, size=info.st_size,
                     mtime=info.st_mtime, sha256="", status="skipped")
    db.add(item)
    if path.suffix.lower() not in ingest.SUPPORTED_EXTENSIONS:
        item.detail = "Not a .txt, .pdf or .docx file"
        return item
    if info.st_size > ingest.MAX_UPLOAD_BYTES:
        item.detail = f"Larger than {ingest.MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        return item

    data = path.read_bytes()
    item.sha256 = hashlib.sha256(data).hexdigest()
    if row.skip_duplicates:
        earlier = db.scalar(select(Source.job_id).where(Source.sha256 == item.sha256).order_by(Source.job_id))
        if earlier is not None:
            item.detail = f"Same file as job #{earlier:04d}"
            item.job_id = earlier
            return item
    try:
        extracted = ingest.from_file(path.name, data)
    except ingest.IngestError as exc:
        item.status, item.detail = "failed", str(exc)
        return item

    outputs = [o for o in (row.outputs or DEFAULT_OUTPUTS) if o in OUTPUT_TYPES]
    job = save_draft(db, [extracted], "", owner, created_via="watch", suggested_outputs=outputs)
    item.status, item.job_id = "drafted", job.id
    found = len(job.safety_json["findings"]) + len(job.safety_json["suspicious"])
    item.detail = f"Draft job #{job.id:04d} · waiting at the Safety check" + (
        f" ({found} thing{'s' if found != 1 else ''} to check)" if found else "")
    if row.notify:
        notifications.notify(db, owner.id, "watch", "Watch folder drafted a report",
                             f"{path.name} · waiting for you at the Safety check", job)
    return item


def check_all() -> None:
    """One round over every switched-on watch folder (called by the background timer)."""
    with SessionLocal() as db:
        for row in db.scalars(select(WatchSettings).where(WatchSettings.enabled.is_(True))).all():
            try:
                check(db, row)
            except Exception:  # one bad folder must not stop the others
                db.rollback()
                log.exception("Watch folder check failed for user %s", row.user_id)


_stop = threading.Event()


def start_timer() -> None:
    """Check every WATCH_INTERVAL_SECONDS in a background thread (0 = never, e.g. in tests)."""
    interval = settings.watch_interval_seconds
    if interval <= 0:
        return

    def loop():
        while not _stop.wait(interval):
            check_all()

    threading.Thread(target=loop, name="pramaan-watch", daemon=True).start()
    log.info("Watch folders are checked every %s seconds", interval)


def stop_timer() -> None:
    _stop.set()


def activity_json(item: WatchFile, job: Job | None) -> dict:
    return {
        "id": item.id, "filename": item.filename, "folder": item.folder, "status": item.status,
        "detail": item.detail, "job_id": item.job_id, "bytes": item.size,
        "job_status": job.status if job is not None else None,
        "found_at": as_utc(item.found_at).isoformat(),
    }


def audit_settings_change(user: User, row: WatchSettings) -> None:
    state = "on" if row.enabled else "off"
    kit = ", ".join(OUTPUT_TYPES[o]["label"] for o in row.outputs if o in OUTPUT_TYPES)
    audit.log("content", "watch_settings", f"Watch folder {state}: data/watch/{row.folder} (kit: {kit})",
              actor=user, target=f"user {user.username}")
