"""Job routes: create a transformation job, list jobs, and read one job's progress and results.

A new transformation has 3 steps (Stage 6A):
POST /api/jobs            1. add sources: read them and run the safety scan; the job is saved as a "draft"
PUT  /api/jobs/{id}/safety  2. safety check: choices for each finding + the TLP label (routes/safety.py)
POST /api/jobs/{id}/start 3. outputs and settings: create the outputs and start the AI in the background
    (POST /api/jobs with `outputs` does all three at once, with the suggested label and default choices:
    handy for scripts and tests)

GET  /api/jobs            list jobs, newest first
GET  /api/jobs/{id}       status, fact sheet, each output as it finishes, checks and scores (the page polls this)
POST /api/jobs/{id}/retry run a failed job again; finished parts are kept
GET  /api/jobs/{id}/sources/{S1}   the text of one source, page by page (for the "Source trace" panel)
GET  /api/options         the output types and setting choices, for the "New transformation" form

Edit, regenerate, versions and file downloads (Word, PDF, slides, ...) are in outputs.py.
Submit for review, the review queue, approve and send back are in review.py.

Who may do what (Stage 6B, checked on every request by app/auth/deps.py):
Operators make and change jobs. Reviewers may read every job (to review it) but not change it.
Admins manage users and do not see job content. While a job is with a reviewer ("in_review") or
approved, nobody can change it.
"""

from datetime import datetime
from typing import Annotated

import copy

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import allow, signed_in
from app.db import Job, Output, Source, User, as_utc, get_session
from app.exporters import FORMATS
from app.pipeline import ingest, runner
from app.pipeline.checks import CHECKS_VERSION, fact_sheet_check, recheck_job
from app.pipeline.output_types import DEFAULT_SETTINGS, OUTPUT_ORDER, OUTPUT_TYPES, SETTING_OPTIONS
from app.pipeline.segments import segments
from app.pipeline.versions import ORIGIN_LABELS, current_version
from app.safety.decisions import decision_json, record
from app.safety.scanner import ScanSource, scan_sources
from app.safety.tlp import switched_off

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/options")
def options(user: User = Depends(signed_in)):
    return {
        "output_types": [
            {"key": key, "label": spec["label"], "description": spec["description"], "public": spec["public"]}
            for key, spec in OUTPUT_TYPES.items()
        ],
        "settings": SETTING_OPTIONS,
        "default_settings": DEFAULT_SETTINGS,
    }


@router.post("/jobs", status_code=201)
async def create_job(
    outputs: Annotated[list[str] | None, Form()] = None,
    title: Annotated[str, Form()] = "",
    text: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
    audience: Annotated[str, Form()] = DEFAULT_SETTINGS["audience"],
    tone: Annotated[str, Form()] = DEFAULT_SETTINGS["tone"],
    objective: Annotated[str, Form()] = DEFAULT_SETTINGS["objective"],
    style: Annotated[str, Form()] = DEFAULT_SETTINGS["style"],
    detail_level: Annotated[str, Form()] = DEFAULT_SETTINGS["detail_level"],
    db: Session = Depends(get_session),
    user: User = Depends(allow("operator")),
):
    """Step 1: read the sources and scan them (no AI). Without `outputs` the job waits as a "draft" for
    the Safety check. With `outputs` it starts at once, using the suggested TLP label."""
    # --- check the form ---
    selected = _selected_outputs(outputs or [], required=False)
    job_settings = _clean_settings(
        {"audience": audience, "tone": tone, "objective": objective, "style": style, "detail_level": detail_level}
    )

    # --- read the sources (fast: no AI yet) ---
    extracted: list[ingest.ExtractedSource] = []
    try:
        if text.strip():
            extracted.append(ingest.from_text(text))
        for upload in files or []:
            if upload.filename:
                extracted.append(ingest.from_file(upload.filename, await upload.read()))
    except ingest.IngestError as exc:
        raise HTTPException(400, str(exc))
    if not extracted:
        raise HTTPException(400, "Paste some text or upload a file (.txt, .pdf or .docx).")

    # --- safety scan (fast: patterns only) ---
    report = scan_sources([ScanSource(f"S{n}", s.filename, s.pages, s.notes) for n, s in enumerate(extracted, start=1)])
    if selected:  # one step: the suggested label must allow the chosen outputs
        _check_allowed(selected, report["suggested_tlp"])

    # --- save the job ---
    job = Job(title=(title.strip() or _guess_title(extracted[0]))[:200], status="draft", step="",
              settings_json=job_settings, safety_json=report, owner_id=user.id)
    db.add(job)
    db.flush()  # gives the job its id

    for number, source in enumerate(extracted, start=1):
        key = f"S{number}"
        pages_path = ingest.save_source(job.id, key, source)
        db.add(Source(job=job, source_key=key, filename=source.filename, kind=source.kind, sha256=source.sha256,
                      text_path=str(pages_path), pages=len(source.pages), chars=source.chars))
    record(db, job, "scan", scan_summary(report), by=None)

    if selected:
        job.tlp = report["suggested_tlp"]
        record(db, job, "tlp", f"TLP:{job.tlp} used as suggested (started in one step, without the Safety check "
                               f"screen). {report['tlp_reason']}", by=user, value=job.tlp)
        start_outputs(db, job, selected, job_settings, user)
    db.commit()

    if selected:
        runner.submit(job.id)
    return job_detail(job)


class StartRequest(BaseModel):
    outputs: list[str]
    settings: dict[str, str] = {}


@router.post("/jobs/{job_id}/start")
def start_job(job_id: int, body: StartRequest, db: Session = Depends(get_session),
              user: User = Depends(allow("operator"))):
    """Step 3: the outputs and settings. Creates the outputs and starts the AI in the background."""
    job = _get_job(db, job_id)
    if job.status != "draft":
        raise HTTPException(409, "This job has already started.")
    if not job.tlp:
        raise HTTPException(400, "Choose a sharing label (TLP) in the Safety check first.")
    selected = _selected_outputs(body.outputs, required=True)
    job_settings = _clean_settings(DEFAULT_SETTINGS | body.settings)
    start_outputs(db, job, selected, job_settings, user)
    db.commit()
    runner.submit(job.id)
    return job_detail(job)


def start_outputs(db: Session, job: Job, selected: list[str], job_settings: dict, user: User) -> None:
    """Create the chosen outputs (short ones first) and mark the job as generating. Public outputs a
    RED / AMBER label does not allow are refused with the reason."""
    _check_allowed(selected, job.tlp)
    off = switched_off(job.tlp)
    job.settings_json = job_settings
    job.status, job.step, job.error = "generating", "Waiting in the queue", None
    # Short outputs first, so the operator sees results sooner.
    for position, output_type in enumerate(o for o in OUTPUT_ORDER if o in selected):
        db.add(Output(job=job, type=output_type, position=position))

    report = copy.deepcopy(job.safety_json or {})
    report["switched_off"] = off
    job.safety_json = report  # a new object, so SQLAlchemy saves the change
    detail = f"Started writing: {_labels(o for o in OUTPUT_ORDER if o in selected)}."
    if off:
        detail += f" Switched off by TLP:{job.tlp}: {_labels(off)}."
    record(db, job, "start", detail, by=user)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_session), user: User = Depends(allow("operator", "reviewer"))):
    jobs = db.scalars(select(Job).order_by(Job.id.desc()).limit(200))
    return [job_summary(job) for job in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("operator", "reviewer"))):
    job = _get_job(db, job_id)
    _bring_up_to_date(db, job)
    return job_detail(job)


@router.get("/jobs/{job_id}/sources/{source_key}")
def get_source_text(job_id: int, source_key: str, db: Session = Depends(get_session),
                    user: User = Depends(allow("operator", "reviewer"))):
    """The extracted text of one source, page by page. Highlight positions (start, end) in the fact
    sheet are character positions in these page texts."""
    job = _get_job(db, job_id)
    source = next((s for s in job.sources if s.source_key == source_key.upper()), None)
    if source is None:
        raise HTTPException(404, f"Source {source_key} of job {job_id} not found.")
    return {"id": source.source_key, "filename": source.filename, "kind": source.kind,
            "pages": ingest.load_pages(source.text_path)}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("operator"))):
    job = _get_job(db, job_id)
    must_be_changeable(job)
    if job.status == "generating":
        raise HTTPException(409, "This job is already running.")
    if job.status == "draft":
        raise HTTPException(409, "This job has not started yet. Finish the safety check and choose the outputs.")
    job.status, job.step, job.error = "generating", "Waiting in the queue", None
    for output in job.outputs:
        if output.status == "failed":
            output.status, output.error = "queued", None
    db.commit()
    runner.submit(job.id)
    return job_detail(job)


# ---- helpers ------------------------------------------------------------------------------


def _selected_outputs(outputs: list[str], required: bool) -> list[str]:
    # A browser may send the outputs as one comma-separated value; accept both forms.
    selected = [o.strip() for value in outputs for o in value.split(",") if o.strip()]
    unknown = [o for o in selected if o not in OUTPUT_TYPES]
    if unknown:
        raise HTTPException(400, f"Unknown output type(s): {', '.join(unknown)}")
    if required and not selected:
        raise HTTPException(400, "Choose at least one output.")
    return selected


def _clean_settings(values: dict) -> dict:
    if values.get("detail_level") not in SETTING_OPTIONS["detail_level"]:
        raise HTTPException(400, "Level of detail must be short, medium or detailed.")
    return {key: str(values.get(key, DEFAULT_SETTINGS[key])).strip()[:100] for key in DEFAULT_SETTINGS}


def _check_allowed(selected: list[str], tlp: str | None) -> None:
    """400 if the label switches off any of the chosen outputs."""
    off = switched_off(tlp)
    blocked = [o for o in selected if o in off]
    if blocked:
        raise HTTPException(400, f"{_labels(blocked)} cannot be made: {off[blocked[0]]} Untick "
                                 f"{'it' if len(blocked) == 1 else 'them'}, or choose TLP:GREEN or TLP:CLEAR.")


def _labels(output_types) -> str:
    return ", ".join(OUTPUT_TYPES[o]["label"] for o in output_types)


def scan_summary(report: dict) -> str:
    """The scan in one line for the decision log, e.g. 'Scanned 2 pages: 4 private items (3 kinds) ...'."""
    parts = [f"{len(report['findings'])} private item{'s' if len(report['findings']) != 1 else ''}"]
    parts.append(f"{len(report['indicators'])} attack indicator{'s' if len(report['indicators']) != 1 else ''}")
    parts.append(f"{len(report['suspicious'])} suspicious instruction{'s' if len(report['suspicious']) != 1 else ''}")
    pages = report["checked"]["pages"]
    return (f"Scanned {pages} page{'s' if pages != 1 else ''}: {', '.join(parts)}. "
            f"Suggested TLP:{report['suggested_tlp']}.")


# Jobs in these states are frozen: the reviewer must see exactly what was submitted.
FROZEN = {
    "in_review": "This job is with a reviewer, so it cannot be changed now. If it is sent back, you can change it again.",
    "approved": "This job is approved, so it cannot be changed any more.",
}


def must_be_changeable(job: Job) -> None:
    if job.status in FROZEN:
        raise HTTPException(409, FROZEN[job.status])


def _get_job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, f"Job {job_id} not found.")
    return job


def _bring_up_to_date(db: Session, job: Job) -> None:
    """Jobs checked by an older version of the checks: work them out again once (no AI)."""
    if job.status == "generating" or job.fact_sheet is None:
        return
    written = [o for o in job.outputs if o.content_json]
    if written and (job.consistency_json is None
                    or any((o.quality_json or {}).get("checks_version") != CHECKS_VERSION for o in written)):
        recheck_job(db, job)


def _guess_title(source: ingest.ExtractedSource) -> str:
    """A title from the text: the first ALL-CAPS heading, else the first real line, else the file name."""
    lines = [line.strip(" #*-\t") for line in "\n".join(source.pages[:3]).splitlines()]
    lines = [line for line in lines if len(line) > 8 and "SAMPLE" not in line.upper()]
    for line in lines[:30]:
        if line.isupper() and len(line.split()) >= 3:
            return line.capitalize()[:120]  # "INCIDENT REPORT: X" -> "Incident report: x"
    return lines[0][:120] if lines else source.filename


def _time(value: datetime | None) -> str | None:
    """Times are stored in UTC; send them as ISO text with the timezone."""
    return as_utc(value).isoformat() if value is not None else None


def review_json(review) -> dict:
    return {"decision": review.decision, "by": review.user.full_name if review.user else None,
            "user_id": review.user_id, "notes": review.notes, "version": review.job_version,
            "created_at": _time(review.created_at)}


def job_summary(job: Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "owner": {"id": job.owner.id, "full_name": job.owner.full_name} if job.owner else None,
        "status": job.status,
        "step": job.step,
        "error": job.error,
        "outputs_done": sum(o.status == "done" for o in job.outputs),
        "outputs_total": len(job.outputs),
        "output_types": [o.type for o in job.outputs],
        "created_at": _time(job.created_at),
        "updated_at": _time(job.updated_at),
    }


def job_detail(job: Job) -> dict:
    return {
        **job_summary(job),
        "tlp": job.tlp,
        # Stage 6B: submitted, approved, sent back (with the reviewer's notes), oldest first
        "reviews": [review_json(r) for r in job.reviews],
        # Stage 6A: the safety report with the operator's choices, every decision, and the public
        # outputs the TLP label switches off ({} = all allowed)
        "safety": job.safety_json,
        "safety_decisions": [decision_json(d) for d in job.safety_decisions],
        "switched_off": switched_off(job.tlp),
        "version": job.version,
        "settings": job.settings_json,
        "quality_score": job.quality_score,
        "consistency": job.consistency_json,
        "sources": [
            {"id": s.source_key, "filename": s.filename, "kind": s.kind, "pages": s.pages, "chars": s.chars, "sha256": s.sha256}
            for s in job.sources
        ],
        "fact_sheet": job.fact_sheet.json if job.fact_sheet else None,
        # how many fact sheet quotes were found in the source; ok = False -> "Do not publish" banner
        "fact_sheet_check": fact_sheet_check(job.fact_sheet.json if job.fact_sheet else None),
        "outputs": [
            {
                "id": o.id,
                "type": o.type,
                "label": OUTPUT_TYPES[o.type]["label"],
                "formats": FORMATS.get(o.type, []),  # file types it can be downloaded as
                "language": o.language,
                "status": o.status,
                "content": o.content_json,  # always the latest version
                "version": current_version(o),
                "origin": o.origin,  # ai | human | regenerated
                "origin_label": ORIGIN_LABELS.get(o.origin, o.origin),
                "quality": o.quality_json,
                "quality_score": o.quality_score,
                # the text fields the operator can edit (see segments.py)
                "fields": [
                    {"path": seg.path, "label": seg.label, "text": seg.text}
                    for seg in segments(o.type, o.content_json or {}) if seg.editable
                ],
                "error": o.error,
                "truncated": o.truncated,
                "seconds": o.seconds,
                "tokens": o.tokens,
                "started_at": _time(o.started_at),
                "finished_at": _time(o.finished_at),
            }
            for o in job.outputs
        ],
    }
