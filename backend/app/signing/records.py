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


# ---- withdrawing --------------------------------------------------------------------------------


class RecordError(ValueError):
    """Something the person can fix; the message is shown as it is."""


def withdraw(db: Session, record_no: str, admin, reason: str, signer) -> Record:
    """Add a signed "withdraw" entry for a record. The record itself is never changed or deleted; the
    verify page shows it as withdrawn, with the reason (for TLP:RED / AMBER only a general reason)."""
    reason = " ".join((reason or "").split())[:500]
    if len(reason) < 5:
        raise RecordError("Write the reason for withdrawing it (at least a few words).")
    key = signer.describe()
    with lock:
        issue = find_issue(db, record_no)
        if issue is None:
            raise RecordError(f"Record {record_no} not found.")
        if withdrawal_of(db, record_no) is not None:
            raise RecordError(f"Record {record_no} is already withdrawn.")
        restricted = json.loads(issue.public_manifest).get("restricted", True)
        at = now_iso()
        manifest = {"format": FORMAT, "kind": "withdraw", "record_no": record_no, "withdrawn_at": at,
                    "reason": reason, "withdrawn_by": {"name": admin.full_name, "role": "Admin", "user_id": admin.id},
                    "signer": key}
        public = {"format": FORMAT, "kind": "withdraw", "record_no": record_no, "withdrawn_at": at,
                  "reason": "Withdrawn by the issuing office." if restricted else reason,
                  "signer": {"key_id": key["key_id"], "algorithm": key["algorithm"]}}
        manifest_text, public_text = canonical(manifest), canonical(public)
        entry = Record(kind="withdraw", record_no=record_no, job_id=issue.job_id, job_version=issue.job_version,
                       created_at=at, created_by=admin.id, manifest=manifest_text,
                       signature=signer.sign(manifest_text.encode("utf-8")), public_manifest=public_text,
                       public_signature=signer.sign(public_text.encode("utf-8")), key_id=key["key_id"])
        append(db, entry)
        db.commit()
    return entry


# ---- checking the whole book --------------------------------------------------------------------


def verify_book(db: Session, public_key_pem: str, check_files: bool = True) -> dict:
    """Check every entry, oldest first:
      - numbered 1, 2, 3 ... with no gap, each pointing to the hash of the one before
      - its own hash matches its content (nothing was changed after it was written)
      - both signatures are valid for the public key (nobody re-wrote and re-hashed it)
      - (check_files) every signed file still on disk has the fingerprint in its manifest
    Returns {"ok": True, "checked": n, "files_checked": m, "last_hash": ...}, or at the first problem
    {"ok": False, "checked": rows before it, "broken": {"seq", "record_no", "reason"}}."""
    from app import crypto
    from app.signing.signer import key_id as key_id_of, verify as verify_signature

    our_key = key_id_of(public_key_pem)
    previous, expected, checked, files_checked = GENESIS, 1, 0, 0
    issued: set[str] = set()
    for entry in db.scalars(select(Record).order_by(Record.seq)).yield_per(200):
        reason = None
        if entry.seq != expected:
            reason = (f"Entry {expected} is missing (deleted?)" if entry.seq > expected
                      else f"Entry {entry.seq} appears twice")
        elif entry.prev_hash != previous:
            reason = "It does not point to the entry before it (an entry before it was changed, removed or added)."
        elif entry_hash(entry) != entry.entry_hash:
            reason = "Its content was changed after it was written."
        elif entry.key_id != our_key:
            reason = "It was signed with a different key than this computer's signing key."
        elif not verify_signature(public_key_pem, entry.manifest.encode("utf-8"), entry.signature):
            reason = "Its signature does not match its content (it was re-written)."
        elif not verify_signature(public_key_pem, entry.public_manifest.encode("utf-8"), entry.public_signature):
            reason = "The signature of its public part does not match."
        elif entry.kind == "withdraw" and entry.record_no not in issued:
            reason = "It withdraws a record that is not in the book."
        elif entry.kind == "issue" and check_files:
            from app.signing.sign_job import signed_dir
            folder = signed_dir(entry.job_id, entry.record_no)
            for f in json.loads(entry.manifest)["files"]:
                path = folder / f["name"]
                if not path.exists():
                    reason = f"The signed file {f['name']} is missing."
                    break
                try:
                    data = crypto.read_file(path)
                except crypto.DecryptionError:
                    reason = f"The signed file {f['name']} was changed (it no longer decrypts)."
                    break
                if hashlib.sha256(data).hexdigest() != f["sha256"]:
                    reason = f"The signed file {f['name']} was changed (its fingerprint differs)."
                    break
                files_checked += 1
        if reason:
            return {"ok": False, "checked": checked, "files_checked": files_checked,
                    "broken": {"seq": entry.seq, "record_no": entry.record_no, "kind": entry.kind, "reason": reason}}
        if entry.kind == "issue":
            issued.add(entry.record_no)
        previous, expected, checked = entry.entry_hash, expected + 1, checked + 1
    return {"ok": True, "checked": checked, "files_checked": files_checked, "last_hash": previous}
