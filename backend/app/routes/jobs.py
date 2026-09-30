"""Job routes: create a transformation job, list jobs, and read one job's progress and results.

POST /api/jobs            create a job (pasted text and/or files + outputs + settings); starts it in the background
GET  /api/jobs            list jobs, newest first
GET  /api/jobs/{id}       status, fact sheet and each output as it finishes (the page polls this)
POST /api/jobs/{id}/retry run a failed job again; finished parts are kept
GET  /api/options         the output types and setting choices, for the "New transformation" form
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Job, Output, Source, get_session
from app.pipeline import ingest, runner
from app.pipeline.output_types import DEFAULT_SETTINGS, OUTPUT_ORDER, OUTPUT_TYPES, SETTING_OPTIONS

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/options")
def options():
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
    outputs: Annotated[list[str], Form()],
    title: Annotated[str, Form()] = "",
    text: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
    audience: Annotated[str, Form()] = DEFAULT_SETTINGS["audience"],
    tone: Annotated[str, Form()] = DEFAULT_SETTINGS["tone"],
    objective: Annotated[str, Form()] = DEFAULT_SETTINGS["objective"],
    style: Annotated[str, Form()] = DEFAULT_SETTINGS["style"],
    detail_level: Annotated[str, Form()] = DEFAULT_SETTINGS["detail_level"],
    db: Session = Depends(get_session),
):
    # --- check the form ---
    # A browser may send the outputs as one comma-separated value; accept both forms.
    selected = [o.strip() for value in outputs for o in value.split(",") if o.strip()]
    unknown = [o for o in selected if o not in OUTPUT_TYPES]
    if unknown:
        raise HTTPException(400, f"Unknown output type(s): {', '.join(unknown)}")
    if not selected:
        raise HTTPException(400, "Choose at least one output.")
    if detail_level not in SETTING_OPTIONS["detail_level"]:
        raise HTTPException(400, "Level of detail must be short, medium or detailed.")
    job_settings = {
        "audience": audience.strip()[:100],
        "tone": tone.strip()[:100],
        "objective": objective.strip()[:100],
        "style": style.strip()[:100],
        "detail_level": detail_level,
    }

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

    # --- save the job ---
    job = Job(title=(title.strip() or _guess_title(extracted[0]))[:200], status="generating",
              step="Waiting in the queue", settings_json=job_settings)
    db.add(job)
    db.flush()  # gives the job its id

    for number, source in enumerate(extracted, start=1):
        key = f"S{number}"
        pages_path = ingest.save_source(job.id, key, source)
        db.add(Source(job=job, source_key=key, filename=source.filename, kind=source.kind, sha256=source.sha256,
                      text_path=str(pages_path), pages=len(source.pages), chars=source.chars))

    # Short outputs first, so the operator sees results sooner.
    for position, output_type in enumerate(o for o in OUTPUT_ORDER if o in selected):
        db.add(Output(job=job, type=output_type, position=position))
    db.commit()

    runner.submit(job.id)
    return job_detail(job)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_session)):
    jobs = db.scalars(select(Job).order_by(Job.id.desc()).limit(200))
    return [job_summary(job) for job in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_session)):
    return job_detail(_get_job(db, job_id))


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_session)):
    job = _get_job(db, job_id)
    if job.status == "generating":
        raise HTTPException(409, "This job is already running.")
    job.status, job.step, job.error = "generating", "Waiting in the queue", None
    for output in job.outputs:
        if output.status == "failed":
            output.status, output.error = "queued", None
    db.commit()
    runner.submit(job.id)
    return job_detail(job)


# ---- helpers ------------------------------------------------------------------------------


def _get_job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, f"Job {job_id} not found.")
    return job


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
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def job_summary(job: Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
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
        "version": job.version,
        "settings": job.settings_json,
        "sources": [
            {"id": s.source_key, "filename": s.filename, "kind": s.kind, "pages": s.pages, "chars": s.chars, "sha256": s.sha256}
            for s in job.sources
        ],
        "fact_sheet": job.fact_sheet.json if job.fact_sheet else None,
        "outputs": [
            {
                "id": o.id,
                "type": o.type,
                "label": OUTPUT_TYPES[o.type]["label"],
                "language": o.language,
                "status": o.status,
                "content": o.content_json,
                "quality": o.quality_json,
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
