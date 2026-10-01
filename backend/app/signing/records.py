"""The record book: every signed document set gets a numbered, signed, hash-chained record.

Record numbers: PRM-<year>-<6 digits>, counting issued records only (PRM-2026-000001, 000002 ...).

Each row of the `records` table:
  - manifest + signature: the full description, signed by the Reviewer's key
  - public_manifest + public_signature: what the public verify page gets (no title for TLP:RED/AMBER)
  - prev_hash: the entry_hash of the row before it (64 zeros for the first)
  - entry_hash: SHA-256 of prev_hash + this row's content
Changing, removing or inserting any row breaks the chain from that row on; verify_book() finds it.
Withdrawing a record adds a new, signed "withdraw" row: nothing is ever changed or deleted.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Record

GENESIS = "0" * 64
FORMAT = "pramaan-record/1"

# One writer at a time: the record number and prev_hash must be read and used together.
lock = threading.Lock()


def canonical(data) -> str:
    """The exact text that is signed: JSON with sorted keys and no extra spaces (UTF-8)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_record_no(db: Session, when: datetime | None = None) -> str:
    issued = db.scalar(select(func.count(Record.seq)).where(Record.kind == "issue"))
    year = (when or datetime.now()).year
    return f"PRM-{year}-{issued + 1:06d}"


def last_entry(db: Session) -> Record | None:
    return db.scalar(select(Record).order_by(Record.seq.desc()).limit(1))


def entry_hash(entry: Record) -> str:
    content = [entry.seq, entry.kind, entry.record_no, entry.job_id, entry.job_version, entry.created_at,
               entry.created_by, entry.manifest, entry.signature, entry.public_manifest, entry.public_signature,
               entry.key_id]
    return sha256_text(entry.prev_hash + canonical(content))


def append(db: Session, entry: Record) -> Record:
    """Give the entry its number and chain hashes, and add it (the caller holds `lock` and commits)."""
    last = last_entry(db)
    entry.seq = last.seq + 1 if last else 1
    entry.prev_hash = last.entry_hash if last else GENESIS
    entry.entry_hash = entry_hash(entry)
    db.add(entry)
    return entry


def find_issue(db: Session, record_no: str) -> Record | None:
    return db.scalar(select(Record).where(Record.kind == "issue", Record.record_no == record_no))


def withdrawal_of(db: Session, record_no: str) -> Record | None:
    return db.scalar(select(Record).where(Record.kind == "withdraw", Record.record_no == record_no))
