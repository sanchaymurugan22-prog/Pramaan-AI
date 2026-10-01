"""Record book routes (Stage 7).

GET /api/records/{record_no}          one record: what was signed, by whom, files and fingerprints, withdrawn?
GET /api/records/{record_no}/qr.png   its QR code (the verify address + record number), as on the files

Operators and Reviewers read records of jobs (as they read the jobs); Admins see the record book.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.deps import allow
from app.db import User, get_session
from app.signing import records
from app.signing.qr import qr_png, verify_url

router = APIRouter(prefix="/api/records", tags=["records"])
READERS = allow("operator", "reviewer", "admin")


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
