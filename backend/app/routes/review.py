"""Review routes (Stage 6B): an Operator submits a finished job, a Reviewer approves it or sends it back.

POST /api/jobs/{id}/submit    Operator: "Submit for review" (ready or sent back -> in_review)
GET  /api/review/queue        Reviewer: jobs waiting for review, and the latest decisions
POST /api/jobs/{id}/review    Reviewer: {"decision": "approve" | "send_back", "notes": "...", "pin": ""}
                              Approve also SIGNS the job (Stage 7, app/signing/sign_job.py): final files with a
                              QR code, fingerprints, a signed record in the record book. pin: DSC token only.
POST /api/jobs/{id}/outputs/{output_id}/native-check  Reviewer (Stage 8): {"checked": true} ticks "Checked by a native
                              speaker" for a translated output; every translation must be ticked before approving
GET  /api/jobs/{id}/sign-info Reviewer: what signing would do (signer, number of outputs and files), for the dialog
POST /api/jobs/{id}/new-version  Operator: reopen an approved job as a new version (needs a new review and signature)

Separation of duties: a Reviewer cannot review a job they worked on (created, edited, made safety
choices for, or submitted), even if they were an Operator when they did it. Someone else must check it.
"""

import json
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, notifications
from app.auth.deps import allow
from app.db import Job, OutputVersion, Record, Review, User, as_utc, get_session, utc_now
from app.exporters import ExportError, ExportTimeout, is_blocked
from app.safety.public_check import check_public_outputs
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
    notifications.notify_reviewers(db, "submitted", f"New for review: {job.title}",
                                   f"v{job.version} · submitted by {user.full_name}", job, except_user=user.id)
    db.commit()
    audit.log("review", "submitted", f"Submitted job #{job.id} v{job.version} for review", actor=user,
              target=f"job {job.id}")
    return job_detail(job)


class ReviewDecision(BaseModel):
    decision: Literal["approve", "send_back"]
    notes: str = ""
    pin: str = ""  # DSC token PIN (SIGNER=dsc only); used once, never stored or logged
    reasons: list[str] = []  # Stage 9B, send back: chips from SEND_BACK_REASONS


# Stage 9B (design 28): why a job is sent back
SEND_BACK_REASONS = ["Facts need checking", "Language quality", "Tone", "Sensitive detail", "Formatting"]


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
    unknown = [r for r in body.reasons if r not in SEND_BACK_REASONS]
    if unknown:
        raise HTTPException(400, f"Unknown reason: {unknown[0]}")
    from app.routes.comments import comments_for  # here: comments.py imports this module
    comments = comments_for(db, job.id, job.version)
    if body.decision == "send_back":
        if len(notes) < 5 and not comments:
            raise HTTPException(400, "Write a note for the Operator, or comment on the lines to change.")
        if body.reasons:
            notes = f"Reasons: {', '.join(body.reasons)}." + (f" {notes}" if notes else "")
        elif not notes:
            notes = f"See the {len(comments)} line comment{'s' if len(comments) != 1 else ''}."

    if body.decision == "approve":
        unchecked = needs_native_check(job)
        if unchecked:
            raise HTTPException(409, "Machine translated - needs a native-speaker check: tick “Checked by a native "
                                     f"speaker” for {', '.join(unchecked)}, or send the job back.")

    decision = "approved" if body.decision == "approve" else "sent_back"
    db.add(Review(job=job, user_id=user.id, decision=decision, notes=notes, job_version=job.version))
    if decision == "approved":
        _, files = outputs_and_files(job)
        notifications.notify(db, job.owner_id, "approved", f"“{job.title}” was approved",
                             f"Approved by {user.full_name}" + (f": “{notes}”" if notes else ""), job)
        try:
            entry = sign_job(db, job, user, body.pin)  # sets "approved" and commits, with the Review row
        except SigningError as exc:
            db.rollback()
            raise HTTPException(409, f"Could not sign: {exc}")
        except ExportError as exc:  # a file could not be made (or took too long): nothing was signed
            db.rollback()
            raise HTTPException(504 if isinstance(exc, ExportTimeout) else 409, f"Could not sign: {exc}")
        # Signing gave the record number: a second note, so the Operator knows the files are final
        notifications.notify(db, job.owner_id, "signed", f"Signed: record {entry.record_no}",
                             f"{user.full_name} signed {files} file{'s' if files != 1 else ''} of “{job.title}”, "
                             "each with its QR code", job)
        db.commit()
        audit.log("review", "approved", f"Approved and signed job #{job.id} v{job.version} as record {entry.record_no} "
                                        f"({files} files)" + (f": “{notes}”" if notes else ""),
                  actor=user, target=f"job {job.id}")
        refresh_demo_site()
    else:
        job.status = decision
        lines = f" · {len(comments)} line comment{'s' if len(comments) != 1 else ''}" if comments else ""
        notifications.notify(db, job.owner_id, "sent_back", f"“{job.title}” was sent back",
                             f"{user.full_name}: “{notes}”{lines}", job)
        db.commit()
        audit.log("review", "sent_back", f"Sent back job #{job.id} v{job.version} with notes: “{notes}”{lines}",
                  actor=user, target=f"job {job.id}")
    return job_detail(job)


def needs_native_check(job: Job) -> list[str]:
    """Stage 8: translated outputs whose current version no Reviewer has ticked yet, e.g. "Advisory (Hindi)"."""
    from app.lang import languages
    return [f"{OUTPUT_TYPES[o.type]['label']} ({languages.get(o.language).name})" for o in job.outputs
            if o.language != "en" and not (o.native_checked_by and o.native_checked_version == o.version)]


class NativeCheck(BaseModel):
    checked: bool = True


@router.post("/jobs/{job_id}/outputs/{output_id}/native-check")
def native_check(job_id: int, output_id: int, body: NativeCheck, db: Session = Depends(get_session),
                 user: User = Depends(allow("reviewer"))):
    """Stage 8: a Reviewer ticks (or unticks) "Checked by a native speaker" for a translated output.
    It is for this version: if the translation changes, it must be checked again."""
    from app.db import Output
    from app.lang import languages

    job = _get_job(db, job_id)
    output = db.get(Output, output_id)
    if output is None or output.job_id != job.id:
        raise HTTPException(404, f"Output {output_id} of job {job_id} not found.")
    if output.language == "en":
        raise HTTPException(400, "Only translated outputs need a native-speaker check.")
    if job.status != "in_review":
        raise HTTPException(409, "The native-speaker check is ticked while the job is being reviewed.")
    if user.id in worked_on_by(db, job):
        raise HTTPException(403, SEPARATION)
    what = f"{OUTPUT_TYPES[output.type]['label']} ({languages.get(output.language).name}) v{output.version}"
    if body.checked:
        output.native_checked_by, output.native_checked_at, output.native_checked_version = user.id, utc_now(), output.version
    else:
        output.native_checked_by = output.native_checked_at = output.native_checked_version = None
    db.commit()
    audit.log("review", "native_check" if body.checked else "native_check_removed",
              f"{'Ticked' if body.checked else 'Removed'} the native-speaker check of the {what} of job #{job.id}",
              actor=user, target=f"job {job.id}")
    return job_detail(job)


@router.post("/jobs/{job_id}/native-check-all")
def native_check_all(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("reviewer"))):
    """Stage 8: tick "Checked by a native speaker" for every translation at once (an emergency alert in 22
    languages), after the Reviewer confirmed that native speakers read them. Each one is recorded."""
    from app.lang import languages

    job = _get_job(db, job_id)
    if job.status != "in_review":
        raise HTTPException(409, "The native-speaker check is ticked while the job is being reviewed.")
    if user.id in worked_on_by(db, job):
        raise HTTPException(403, SEPARATION)
    ticked = []
    for output in job.outputs:
        if output.language != "en" and not (output.native_checked_by and output.native_checked_version == output.version):
            output.native_checked_by, output.native_checked_at, output.native_checked_version = user.id, utc_now(), output.version
            ticked.append(f"{OUTPUT_TYPES[output.type]['label']} ({languages.get(output.language).name}) v{output.version}")
    db.commit()
    if ticked:
        audit.log("review", "native_check", f"Ticked the native-speaker check of {len(ticked)} translations of job "
                                            f"#{job.id} at once: {', '.join(ticked)}", actor=user, target=f"job {job.id}")
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
        "stats": queue_stats(db),
        "signed_today": signed_today(db),
        "signer": _signer_card(user),
        "reasons": SEND_BACK_REASONS,
        # emergency alerts first (fast-track), then waiting longest first
        "waiting": sorted((_queue_item(db, job, user) for job in waiting),
                          key=lambda item: (not item["fast_track"], item["submitted_at"] or "")),
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
        "fast_track": job.created_via == "emergency",  # Stage 9A emergency alert
        "leaks": sum(len((o.quality_json or {}).get("leaks", [])) for o in job.outputs),
        "public_problems": len(check_public_outputs(job.outputs)["problems"]),
        "languages": sorted({o.language for o in job.outputs}) or ["en"],
        "alert": job.alert_json,
        "can_review": not mine,
        "why_not": SEPARATION if mine else None,
    }


# ---- Stage 9B: the Reviewer dashboard (design 24) -------------------------------------------------


def _start_of_today() -> datetime:
    """Midnight today on this computer's clock (record times are stored with their timezone)."""
    local = datetime.now().astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def queue_stats(db: Session) -> dict:
    """Waiting, signed today, average review time this week, sent back this week."""
    week_ago = utc_now() - timedelta(days=7)
    today = _start_of_today()
    waiting = db.scalars(select(Job).where(Job.status == "in_review")).all()
    submitted_times = []
    for job in waiting:
        sub = next((r for r in reversed(job.reviews) if r.decision == "submitted"), None)
        if sub:
            submitted_times.append(as_utc(sub.created_at))
    # review time: from each submission to the decision that followed it
    minutes = []
    for decision in db.scalars(select(Review).where(Review.decision.in_(("approved", "sent_back")))):
        if as_utc(decision.created_at) < week_ago:
            continue
        before = [r for r in decision.job.reviews if r.decision == "submitted" and r.id < decision.id]
        if before:
            minutes.append((as_utc(decision.created_at) - as_utc(before[-1].created_at)).total_seconds() / 60)
    signed = [r for r in db.scalars(select(Record).where(Record.kind == "issue").order_by(Record.seq))
              if datetime.fromisoformat(r.created_at) >= today]
    last_files = len(json.loads(signed[-1].manifest)["files"]) if signed else 0
    sent_back = db.scalars(select(Review).where(Review.decision == "sent_back")).all()
    return {
        "waiting": len(waiting),
        "oldest_submitted_at": min(submitted_times).isoformat() if submitted_times else None,
        "signed_today": len(signed),
        "files_in_last_kit": last_files,
        "average_review_minutes": round(sum(minutes) / len(minutes)) if minutes else None,
        "sent_back_this_week": sum(as_utc(r.created_at) >= week_ago for r in sent_back),
    }


def signed_today(db: Session) -> list[dict]:
    today = _start_of_today()
    rows = [r for r in db.scalars(select(Record).where(Record.kind == "issue").order_by(Record.seq.desc()))
            if datetime.fromisoformat(r.created_at) >= today]
    return [{"record_no": r.record_no, "title": json.loads(r.manifest)["title"], "job_id": r.job_id} for r in rows[:8]]


def _signer_card(user: User) -> dict:
    """The "DSC token" card: which key signs (the test key on this computer, or a DSC token)."""
    try:
        signer = get_signer().describe()
        return {"ready": True, **signer, "holder": user.full_name, "dsc_holder": bool(user.dsc_holder)}
    except SigningError as exc:
        return {"ready": False, "kind": "dsc", "label": "Class 3 DSC on a USB token", "error": str(exc),
                "holder": user.full_name, "dsc_holder": bool(user.dsc_holder)}
