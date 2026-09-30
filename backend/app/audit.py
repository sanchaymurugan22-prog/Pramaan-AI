"""The audit trail (Stage 6B): a permanent record of who did what, and when.

How the hash chain works:
- Every row gets the next number (seq 1, 2, 3 ...) and stores prev_hash = the entry_hash of the row
  before it (row 1 uses 64 zeros).
- entry_hash = SHA-256 of prev_hash + this row's content (number, time, who, what, detail).
- verify() walks the rows in order and works every hash out again. If anyone changed a row, deleted
  one, or put one in, the first row where the numbers no longer match is reported.
- The database also refuses UPDATE and DELETE on this table (see protect_audit_log in db.py).

Rows are written in their own database session, one at a time (a lock keeps two requests from taking
the same number). Nothing secret is ever written here: no passwords, keys, tokens or hidden values.
"""

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import AuditEntry, SessionLocal, User

GENESIS = "0" * 64
SYSTEM = "System"
CATEGORIES = ("security", "users", "content", "review", "system")

_lock = threading.Lock()


def _content_hash(entry: AuditEntry) -> str:
    """SHA-256 over the previous row's hash and everything this row says, in a fixed order."""
    content = [entry.seq, entry.created_at, entry.actor_id, entry.actor, entry.category, entry.action,
               entry.target, entry.detail]
    text = entry.prev_hash + json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def log(category: str, action: str, detail: str, *, actor: User | None = None, actor_name: str | None = None,
        target: str = "") -> AuditEntry:
    """Add one row. actor: the signed-in user (None = the system, or actor_name for someone not signed in)."""
    assert category in CATEGORIES, category
    with _lock, SessionLocal() as db:
        last = db.scalar(select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1))
        entry = AuditEntry(
            seq=last.seq + 1 if last else 1,
            created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            actor_id=actor.id if actor else None,
            actor=(actor.full_name if actor else actor_name or SYSTEM)[:100],
            category=category,
            action=action[:40],
            target=target[:100],
            detail=detail,
            prev_hash=last.entry_hash if last else GENESIS,
        )
        entry.entry_hash = _content_hash(entry)
        db.add(entry)
        db.commit()
        return entry


def log_decisions(user: User, job, decisions) -> None:
    """The safety decisions just saved for a job (scan, choices, TLP label, start), one row each."""
    for decision in decisions:
        log("content", f"safety_{decision.action}", decision.detail, actor=user if decision.user_id else None,
            target=f"job {job.id}")


# ---- checking the chain ------------------------------------------------------------------------


def verify(db: Session) -> dict:
    """Work out every hash again. {"ok": True, "checked": N, "last_hash": ...} or, at the first
    broken row, {"ok": False, "checked": rows before it, "broken": {"seq": n, "reason": "..."}}."""
    previous, expected, checked = GENESIS, 1, 0
    for entry in db.scalars(select(AuditEntry).order_by(AuditEntry.seq)).yield_per(500):
        reason = None
        if entry.seq != expected:
            reason = (f"Row {expected} is missing (deleted?)" if entry.seq > expected
                      else f"Row {entry.seq} appears twice")
        elif entry.prev_hash != previous:
            reason = "It does not point to the row before it (a row before it was changed, removed or added)."
        elif _content_hash(entry) != entry.entry_hash:
            reason = "Its content was changed after it was written."
        if reason:
            return {"ok": False, "checked": checked, "broken": {"seq": entry.seq, "reason": reason,
                                                                "entry": entry_json(entry)}}
        previous, expected, checked = entry.entry_hash, expected + 1, checked + 1
    return {"ok": True, "checked": checked, "last_hash": previous}


# ---- reading it back (Admin screen) --------------------------------------------------------------


def entry_json(entry: AuditEntry) -> dict:
    return {
        "seq": entry.seq,
        "created_at": entry.created_at,
        "actor": entry.actor,
        "actor_id": entry.actor_id,
        "category": entry.category,
        "action": entry.action,
        "target": entry.target,
        "detail": entry.detail,
        "prev_hash": entry.prev_hash,
        "entry_hash": entry.entry_hash,
    }


def search(db: Session, *, category: str = "", text: str = "", actor: str = "", days: int = 0,
           limit: int = 50, offset: int = 0) -> dict:
    """Newest first. days: only the last N days (0 = all). actor: an exact name from the list."""
    query = select(AuditEntry)
    if category in CATEGORIES:
        query = query.where(AuditEntry.category == category)
    if actor:
        query = query.where(AuditEntry.actor == actor)
    if days > 0:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="milliseconds")
        query = query.where(AuditEntry.created_at >= since)  # ISO text in UTC sorts like the time itself
    if text.strip():
        like = f"%{text.strip()}%"
        query = query.where(or_(AuditEntry.detail.ilike(like), AuditEntry.actor.ilike(like),
                                AuditEntry.target.ilike(like), AuditEntry.action.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(AuditEntry.seq.desc()).limit(min(limit, 200)).offset(offset))
    actors = db.scalars(select(AuditEntry.actor).distinct().order_by(AuditEntry.actor))
    return {"entries": [entry_json(e) for e in rows], "total": total, "actors": list(actors)}
