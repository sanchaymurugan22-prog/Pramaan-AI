"""The search box at the top of every page (Stage 9A): one query across jobs, sources and records.

GET /api/search?q=ransom   {"jobs": [...], "sources": [...], "records": [...]}  (at most 6 of each)

Jobs match on the title or the job number ("142", "#0142"); sources on the file name or the start of
their SHA-256 fingerprint; records on the record number or the title. Text INSIDE sources is not
searched: it is stored encrypted, and decrypting every file for each key press would be slow.
Admins do not see job content (Stage 6B), so they get records only.
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import signed_in
from app.db import Job, Record, Source, User, get_session
from app.routes.jobs import matches_text
from app.signing import records

router = APIRouter(prefix="/api", tags=["search"])
LIMIT = 6


@router.get("/search")
def search(q: str = "", db: Session = Depends(get_session), user: User = Depends(signed_in)):
    text = q.strip()
    found: dict[str, list] = {"jobs": [], "sources": [], "records": []}
    if len(text) < 2:
        return found

    if user.role in ("operator", "reviewer"):
        for job in db.scalars(select(Job).where(matches_text(text)).order_by(Job.id.desc()).limit(LIMIT)):
            found["jobs"].append({"id": job.id, "title": job.title, "status": job.status, "tlp": job.tlp,
                                  "version": job.version})
        source_match = Source.filename.ilike(f"%{text}%")
        if len(text) >= 8 and all(c in "0123456789abcdefABCDEF" for c in text):
            source_match = source_match | Source.sha256.startswith(text.lower())
        for source in db.scalars(select(Source).where(source_match).order_by(Source.id.desc()).limit(LIMIT)):
            found["sources"].append({"job_id": source.job_id, "job_title": source.job.title, "id": source.source_key,
                                     "filename": source.filename, "kind": source.kind, "pages": source.pages})

    needle = text.lower()
    for entry in db.scalars(select(Record).where(Record.kind == "issue").order_by(Record.seq.desc())):
        manifest = json.loads(entry.manifest)
        if needle in entry.record_no.lower() or needle in manifest["title"].lower():
            withdrawn = records.withdrawal_of(db, entry.record_no) is not None
            found["records"].append({"record_no": entry.record_no, "title": manifest["title"], "job_id": entry.job_id,
                                     "tlp": manifest["tlp"], "withdrawn": withdrawn})
            if len(found["records"]) >= LIMIT:
                break
    return found
