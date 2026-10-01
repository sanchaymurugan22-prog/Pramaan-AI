"""Record book routes (Stage 7).

GET  /api/records                     Reviewer, Admin: every record, newest first (?q= search, ?status=active|withdrawn|replaced)
POST /api/records/verify              Reviewer, Admin: check the whole record book (chain, signatures, signed files)
GET  /api/records/public-key.pem      anyone signed in: the public key that checks the signatures
GET  /api/records/{record_no}         one record: what was signed, by whom, files and fingerprints, withdrawn?
GET  /api/records/{record_no}/qr.png  its QR code (the verify address + record number), as on the files
POST /api/admin/records/{record_no}/withdraw   Admin: {"reason": "..."} adds a signed withdrawal (never deletes)
GET  /api/admin/records/verify-bundle.zip      Admin: the public verify site with the latest records, for USB transfer

Operators read the records of jobs (as they read the jobs); the book itself is for Reviewers and Admins.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth.deps import allow
from app.db import AuditEntry, Record, User, get_session
from app.signing import records
from app.signing.publish import bundle_zip, refresh_demo_site
from app.signing.qr import qr_png, verify_url
from app.signing.signer import SigningError, get_signer

router = APIRouter(prefix="/api/records", tags=["records"])
admin_router = APIRouter(prefix="/api/admin/records", tags=["records"])
READERS = allow("operator", "reviewer", "admin")
BOOK_READERS = allow("reviewer", "admin")


def record_json(db: Session, entry) -> dict:
    manifest = json.loads(entry.manifest)
    withdrawn = records.withdrawal_of(db, entry.record_no)
    return {
        "seq": entry.seq,
        "record_no": entry.record_no,
        "job_id": entry.job_id,
        "job_version": entry.job_version,
        "title": manifest["title"],
        "tlp": manifest["tlp"],
        "issued_at": manifest["issued_at"],
        "issuing_office": manifest["issuing_office"],
        "approved_by": manifest["approved_by"]["name"],
        "signer": manifest["signer"],
        "replaces": manifest["replaces"],
        "files": manifest["files"],
        "texts": manifest["texts"],
        "verify_url": verify_url(entry.record_no),
        "fingerprint": entry.entry_hash,
        "prev_hash": entry.prev_hash,
        "withdrawn": json.loads(withdrawn.manifest) | {"at": withdrawn.created_at} if withdrawn else None,
    }


def _status(item: dict) -> str:
    if item["withdrawn"]:
        return "withdrawn"
    return "replaced" if item.get("replaced_by") else "active"


@router.get("")
def list_records(q: str = "", status: str = "", db: Session = Depends(get_session), user: User = Depends(BOOK_READERS)):
    entries = db.scalars(select(Record).where(Record.kind == "issue").order_by(Record.seq.desc())).all()
    items = [record_json(db, e) for e in entries]
    replaced_by = {i["replaces"]: i["record_no"] for i in items if i["replaces"]}
    for item in items:
        item["replaced_by"] = replaced_by.get(item["record_no"])
        item["status"] = _status(item)
        item["files_count"] = len(item.pop("files"))
        item["texts_count"] = len(item.pop("texts"))
    counts = {s: sum(i["status"] == s for i in items) for s in ("active", "withdrawn", "replaced")}
    if q.strip():
        needle = q.strip().lower()
        items = [i for i in items if needle in i["record_no"].lower() or needle in i["title"].lower()]
    if status in counts:
        items = [i for i in items if i["status"] == status]
    last = db.scalar(select(AuditEntry).where(AuditEntry.action == "records_verified")
                     .order_by(AuditEntry.seq.desc()).limit(1))
    total_entries = db.scalar(select(Record.seq).order_by(Record.seq.desc()).limit(1)) or 0
    latest = db.scalars(select(Record).order_by(Record.seq.desc()).limit(4)).all()
    return {
        "records": items,
        "counts": counts,
        "entries": total_entries,
        "last_check": {"at": last.created_at, "by": last.actor, "detail": last.detail} if last else None,
        # the newest entries of the chain, oldest first (design 37: cards linked by their hashes)
        "chain": [{"seq": e.seq, "kind": e.kind, "record_no": e.record_no, "created_at": e.created_at,
                   "entry_hash": e.entry_hash, "prev_hash": e.prev_hash,
                   "title": json.loads(e.manifest).get("title") if e.kind == "issue" else None}
                  for e in reversed(latest)],
    }


@router.post("/verify")
def verify_records(db: Session = Depends(get_session), user: User = Depends(BOOK_READERS)):
    try:
        public_key = get_signer().public_key_pem()
    except SigningError as exc:
        raise HTTPException(409, str(exc))
    result = records.verify_book(db, public_key)
    if result["ok"]:
        detail = (f"Record book checked · {result['checked']} of {result['checked']} entries intact, "
                  f"{result['files_checked']} signed files match")
    else:
        detail = f"Record book checked · BROKEN at entry {result['broken']['seq']}: {result['broken']['reason']}"
    audit.log("security", "records_verified", detail, actor=user)
    return result


@router.get("/public-key.pem")
def public_key(user: User = Depends(READERS)):
    try:
        pem = get_signer().public_key_pem()
    except SigningError as exc:
        raise HTTPException(409, str(exc))
    return Response(pem, media_type="application/x-pem-file",
                    headers={"Content-Disposition": 'attachment; filename="pramaan-public-key.pem"'})


class Withdrawal(BaseModel):
    reason: str


@admin_router.post("/{record_no}/withdraw")
def withdraw_record(record_no: str, form: Withdrawal, db: Session = Depends(get_session),
                    admin: User = Depends(allow("admin"))):
    try:
        records.withdraw(db, record_no.upper(), admin, form.reason, get_signer())
    except records.RecordError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 400, str(exc))
    except SigningError as exc:
        raise HTTPException(409, f"Could not sign the withdrawal: {exc}")
    audit.log("review", "record_withdrawn", f"Withdrew record {record_no.upper()}: “{' '.join(form.reason.split())}”",
              actor=admin, target=f"record {record_no.upper()}")
    refresh_demo_site()
    return record_json(db, _issue(db, record_no))


@admin_router.get("/verify-bundle.zip")
def verify_bundle(db: Session = Depends(get_session), admin: User = Depends(allow("admin"))):
    try:
        data = bundle_zip(db)
    except SigningError as exc:
        raise HTTPException(409, str(exc))
    audit.log("security", "verify_bundle_exported", "Exported the public verify bundle (records.json + public key)",
              actor=admin)
    name = f"pramaan-verify-bundle-{records.now_iso()[:10]}.zip"
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


def _issue(db: Session, record_no: str):
    entry = records.find_issue(db, record_no.upper())
    if entry is None:
        raise HTTPException(404, f"Record {record_no} not found.")
    return entry


@router.get("/{record_no}")
def get_record(record_no: str, db: Session = Depends(get_session), user: User = Depends(READERS)):
    return record_json(db, _issue(db, record_no))


@router.get("/{record_no}/qr.png")
def record_qr(record_no: str, db: Session = Depends(get_session), user: User = Depends(READERS)):
    entry = _issue(db, record_no)
    return Response(qr_png(verify_url(entry.record_no), 8), media_type="image/png",
                    headers={"Cache-Control": "no-store"})
