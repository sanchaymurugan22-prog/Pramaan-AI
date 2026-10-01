"""Review routes (Stage 6B): an Operator submits a finished job, a Reviewer approves it or sends it back.

POST /api/jobs/{id}/submit    Operator: "Submit for review" (ready or sent back -> in_review)
GET  /api/review/queue        Reviewer: jobs waiting for review, and the latest decisions
POST /api/jobs/{id}/review    Reviewer: {"decision": "approve" | "send_back", "notes": "...", "pin": ""}
                              Approve also SIGNS the job (Stage 7, app/signing/sign_job.py): final files with a
                              QR code, fingerprints, a signed record in the record book. pin: DSC token only.
GET  /api/jobs/{id}/sign-info Reviewer: what signing would do (signer, number of outputs and files), for the dialog
POST /api/jobs/{id}/new-version  Operator: reopen an approved job as a new version (needs a new review and signature)

Separation of duties: a Reviewer cannot review a job they worked on (created, edited, made safety
choices for, or submitted), even if they were an Operator when they did it. Someone else must check it.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth.deps import allow
from app.db import Job, OutputVersion, Review, User, get_session
from app.exporters import is_blocked
from app.pipeline.checks import fact_sheet_check
from app.pipeline.output_types import OUTPUT_TYPES
from app.routes.jobs import _get_job, _time, job_detail, review_json
from app.signing.publish import refresh_demo_site
from app.signing.sign_job import outputs_and_files, sign_job
from app.signing.signer import SigningError, get_signer

router = APIRouter(prefix="/api", tags=["review"])


class SubmitRequest(BaseModel):
    notes: str = ""


@router.post("/jobs/{job_id}/submit")
def submit_for_review(job_id: int, body: SubmitRequest, db: Session = Depends(get_session),
                      user: User = Depends(allow("operator"))):
    job = _get_job(db, job_id)
    if job.status == "in_review":
        raise HTTPException(409, "This job is already with a reviewer.")
    if job.status == "approved":
        raise HTTPException(409, "This job is already approved.")
    if job.status not in ("ready", "sent_back"):
        raise HTTPException(409, "Only a finished job can be submitted for review.")
    not_done = [OUTPUT_TYPES[o.type]["label"] for o in job.outputs if o.status != "done"]
    if not job.outputs or not_done:
        raise HTTPException(409, f"Some outputs are not finished: {', '.join(not_done)}. Use 'Try again' first.")
    blocked = [OUTPUT_TYPES[o.type]["label"] for o in job.outputs if is_blocked(o)]
    if blocked:
        raise HTTPException(409, f"Private data was found in: {', '.join(blocked)}. Edit it out before submitting.")

    if job.status == "sent_back":
        job.version += 1  # the changed job goes back as a new version: "v2" (a reopened job already has its number)
    job.status = "in_review"
    db.add(Review(job=job, user_id=user.id, decision="submitted", notes=body.notes.strip()[:2000],
                  job_version=job.version))
    db.commit()
    audit.log("review", "submitted", f"Submitted job #{job.id} v{job.version} for review", actor=user,
              target=f"job {job.id}")
    return job_detail(job)


class ReviewDecision(BaseModel):
    decision: Literal["approve", "send_back"]
    notes: str = ""
    pin: str = ""  # DSC token PIN (SIGNER=dsc only); used once, never stored or logged


def worked_on_by(db: Session, job: Job) -> set[int]:
    """Everyone who made or changed this job."""
    people = {job.owner_id}
    people |= {d.user_id for d in job.safety_decisions}
    people |= {r.user_id for r in job.reviews if r.decision in ("submitted", "reopened")}
    output_ids = [o.id for o in job.outputs]
    if output_ids:
        people |= set(db.scalars(select(OutputVersion.created_by).where(OutputVersion.output_id.in_(output_ids))))
    return {p for p in people if p is not None}


SEPARATION = ("You worked on this job, so you cannot review it. Another Reviewer must check it "
              "(separation of duties).")


@router.post("/jobs/{job_id}/review")
def review_job(job_id: int, body: ReviewDecision, db: Session = Depends(get_session),
               user: User = Depends(allow("reviewer"))):
    job = _get_job(db, job_id)
    if job.status != "in_review":
        raise HTTPException(409, "This job is not waiting for review.")
    if user.id in worked_on_by(db, job):
        audit.log("security", "review_refused", f"Tried to review job #{job.id}, which they worked on "
                                                "(refused: separation of duties)", actor=user, target=f"job {job.id}")
        raise HTTPException(403, SEPARATION)
    notes = body.notes.strip()[:4000]
    if body.decision == "send_back" and len(notes) < 5:
        raise HTTPException(400, "Write a note for the Operator: what should be changed?")

    decision = "approved" if body.decision == "approve" else "sent_back"
    db.add(Review(job=job, user_id=user.id, decision=decision, notes=notes, job_version=job.version))
    if decision == "approved":
        try:
            entry = sign_job(db, job, user, body.pin)  # sets "approved" and commits, with the Review row
        except SigningError as exc:
            db.rollback()
            raise HTTPException(409, f"Could not sign: {exc}")
        _, files = outputs_and_files(job)
        audit.log("review", "approved", f"Approved and signed job #{job.id} v{job.version} as record {entry.record_no} "
                                        f"({files} files)" + (f": “{notes}”" if notes else ""),
                  actor=user, target=f"job {job.id}")
        refresh_demo_site()
    else:
        job.status = decision
        db.commit()
        audit.log("review", "sent_back", f"Sent back job #{job.id} v{job.version} with notes: “{notes}”",
                  actor=user, target=f"job {job.id}")
    return job_detail(job)


@router.get("/jobs/{job_id}/sign-info")
def sign_info(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("reviewer"))):
    """For the sign dialog: who signs with what, and how much."""
    job = _get_job(db, job_id)
    outputs, files = outputs_and_files(job)
    try:
        signer = get_signer().describe()
    except SigningError as exc:
        signer = {"kind": "dsc", "label": "Class 3 DSC on a USB token (PKCS#11) - NOT TESTED", "error": str(exc)}
    return {"job_id": job.id, "version": job.version, "outputs": outputs, "files": files, "signer": signer,
            "needs_pin": signer.get("kind") == "dsc", "signed_by": user.full_name}


@router.post("/jobs/{job_id}/new-version")
def new_version(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("operator"))):
    """Reopen an approved (signed) job so it can be changed. Its record stays valid until the new
    version is signed (the new record says it replaces the old one) or an Admin withdraws it."""
    job = _get_job(db, job_id)
    if job.status != "approved":
        raise HTTPException(409, "Only an approved job can be reopened as a new version.")
    job.version += 1
    job.status = "ready"
    db.add(Review(job=job, user_id=user.id, decision="reopened", notes=f"Reopened after record {job.record_no}",
                  job_version=job.version))
    db.commit()
    audit.log("review", "reopened", f"Reopened job #{job.id} as v{job.version} (record {job.record_no} stays until "
                                    "replaced or withdrawn)", actor=user, target=f"job {job.id}")
    return job_detail(job)


@router.get("/review/queue")
def review_queue(db: Session = Depends(get_session), user: User = Depends(allow("reviewer"))):
    waiting = db.scalars(select(Job).where(Job.status == "in_review")).all()
    recent = db.scalars(
        select(Review).where(Review.decision.in_(("approved", "sent_back"))).order_by(Review.id.desc()).limit(10)
    ).all()
    return {
        # waiting longest first
        "waiting": sorted((_queue_item(db, job, user) for job in waiting), key=lambda item: item["submitted_at"] or ""),
        "recent": [review_json(r) | {"job_id": r.job_id, "job_title": r.job.title} for r in recent],
    }


def _queue_item(db: Session, job: Job, reviewer: User) -> dict:
    submitted = next((r for r in reversed(job.reviews) if r.decision == "submitted"), None)
    warnings = sum(len((o.quality_json or {}).get("unlinked", [])) for o in job.outputs)
    sheet_check = fact_sheet_check(job.fact_sheet.json if job.fact_sheet else None)
    mine = reviewer.id in worked_on_by(db, job)
    return {
        "id": job.id,
        "title": job.title,
        "tlp": job.tlp,
        "version": job.version,
        "owner": job.owner.full_name if job.owner else None,
        "submitted_by": submitted.user.full_name if submitted and submitted.user else None,
        "submitted_at": _time(submitted.created_at) if submitted else None,
        "submit_notes": submitted.notes if submitted else "",
        "outputs": [OUTPUT_TYPES[o.type]["label"] for o in job.outputs],
        "quality_score": job.quality_score,
        "warnings": warnings,  # sentences not linked to the source
        "numbers_match": (job.consistency_json or {}).get("ok", True),
        "fact_sheet_ok": sheet_check["ok"] if sheet_check else True,
        "can_review": not mine,
        "why_not": SEPARATION if mine else None,
    }
