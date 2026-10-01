"""Output routes: human edits, regenerating one output, old versions, and file downloads.

PUT  /api/jobs/{id}/outputs/{output_id}                  save the operator's edits as a new version, then re-check (no AI)
POST /api/jobs/{id}/outputs/{output_id}/regenerate       write this one output again from the same fact sheet
GET  /api/jobs/{id}/outputs/{output_id}/versions         every version: number, who made it, score, time
GET  /api/jobs/{id}/outputs/{output_id}/versions/{n}     one old version's text and checks

GET /api/jobs/{id}/outputs/{output_id}/download?format=pdf   one file (docx | pdf | pptx | png | srt | txt)
    add &inline=true to show it in the browser instead of saving it (used for the infographic preview)
GET /api/jobs/{id}/kit.zip                                     every finished output of the job in one .zip

Files are made from the LATEST version, in memory, on each download; an encrypted copy is kept under
data/jobs/<id>/exports/.

Stage 6B: editing and regenerating are for Operators, and only while the job is not with a reviewer
or approved. Operators and Reviewers may read versions and download files.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import audit
from app.auth.deps import allow
from app.db import Job, Output, User, get_session
from app.exporters import MEDIA_TYPES, ExportedFile, ExportError, export_output
from app.exporters.kit import build_kit
from app.pipeline import runner
from app.pipeline.checks import recheck_job
from app.pipeline.generate import add_timings
from app.pipeline.output_types import OUTPUT_TYPES
from app.pipeline.segments import EditError, apply_edits
from app.pipeline.versions import ORIGIN_LABELS, save_version, version_summary
from app.routes.jobs import _time, job_detail, must_be_changeable
from app.signing.sign_job import signed_file, signed_kit

router = APIRouter(prefix="/api", tags=["outputs"])


class FieldEdit(BaseModel):
    path: list[str | int]  # e.g. ["tweets", 1, "text"] (from "fields" in the job details)
    text: str


class OutputEdit(BaseModel):
    fields: list[FieldEdit]


def _get_output(db: Session, job_id: int, output_id: int) -> tuple[Job, Output]:
    job = db.get(Job, job_id)
    output = db.get(Output, output_id)
    if job is None or output is None or output.job_id != job_id:
        raise HTTPException(404, f"Output {output_id} of job {job_id} not found.")
    return job, output


def _label(output: Output) -> str:
    return OUTPUT_TYPES[output.type]["label"]


def _must_be_editable(job: Job, output: Output) -> None:
    must_be_changeable(job)
    if job.status == "generating":
        raise HTTPException(409, "The AI is still working on this job. Wait until it has finished.")
    if output.status != "done" or not output.content_json:
        raise HTTPException(409, "This output is not finished yet.")


@router.put("/jobs/{job_id}/outputs/{output_id}")
def edit_output(job_id: int, output_id: int, edit: OutputEdit, db: Session = Depends(get_session),
                user: User = Depends(allow("operator"))):
    """Save the operator's changes as a new version ("Edited by human") and run every check again.
    The old version is kept. No AI call."""
    job, output = _get_output(db, job_id, output_id)
    _must_be_editable(job, output)
    try:
        content = apply_edits(output.type, output.content_json, [(f.path, f.text) for f in edit.fields])
    except EditError as exc:
        raise HTTPException(400, str(exc))
    if output.type == "video_package":
        add_timings(content)  # the narration changed, so the scene times and subtitles change too
    if content == output.content_json:
        raise HTTPException(400, "Nothing was changed.")

    save_version(db, output, content, "human", by=user)
    output.truncated = False  # a person has now read and fixed the text
    output.error = None
    db.commit()
    audit.log("content", "output_edited", f"Edited the {_label(output)} of job #{job.id} (now version {output.version})",
              actor=user, target=f"job {job.id}")
    recheck_job(db, job)
    return job_detail(job)


@router.post("/jobs/{job_id}/outputs/{output_id}/regenerate")
def regenerate_output(job_id: int, output_id: int, db: Session = Depends(get_session),
                      user: User = Depends(allow("operator"))):
    """Write this one output again from the same fact sheet (in the background, like a new job).
    The current text stays until the new one is ready, and is kept as an older version."""
    job, output = _get_output(db, job_id, output_id)
    _must_be_editable(job, output)
    output.status, output.error, output.started_at = "queued", None, None
    job.status, job.step, job.error = "generating", "Waiting in the queue", None
    db.commit()
    audit.log("content", "output_regenerate", f"Asked the AI to write the {_label(output)} of job #{job.id} again",
              actor=user, target=f"job {job.id}")
    runner.submit(job.id)
    return job_detail(job)


@router.get("/jobs/{job_id}/outputs/{output_id}/versions")
def list_versions(job_id: int, output_id: int, db: Session = Depends(get_session),
                  user: User = Depends(allow("operator", "reviewer"))):
    _, output = _get_output(db, job_id, output_id)
    versions = [version_summary(v) | {"created_at": _time(v.created_at)} for v in reversed(output.versions)]
    if not versions and output.content_json:  # finished before Stage 5: the one version there is
        versions = [{"version": 1, "origin": output.origin, "origin_label": ORIGIN_LABELS.get(output.origin, ""),
                     "quality_score": output.quality_score, "created_at": _time(output.finished_at)}]
    return versions


@router.get("/jobs/{job_id}/outputs/{output_id}/versions/{number}")
def get_version(job_id: int, output_id: int, number: int, db: Session = Depends(get_session),
                user: User = Depends(allow("operator", "reviewer"))):
    _, output = _get_output(db, job_id, output_id)
    version = next((v for v in output.versions if v.version == number), None)
    if version is None:
        raise HTTPException(404, f"Version {number} of this output not found.")
    return version_summary(version) | {"created_at": _time(version.created_at), "content": version.content_json,
                                       "quality": version.quality_json}


@router.get("/jobs/{job_id}/outputs/{output_id}/download")
def download_output(
    job_id: int,
    output_id: int,
    fmt: Annotated[str, Query(alias="format", description="docx, pdf, pptx, png, srt or txt")],
    inline: bool = False,
    db: Session = Depends(get_session),
    user: User = Depends(allow("operator", "reviewer")),
):
    job = db.get(Job, job_id)
    output = db.get(Output, output_id)
    if job is None or output is None or output.job_id != job_id:
        raise HTTPException(404, f"Output {output_id} of job {job_id} not found.")
    fmt = fmt.lower().lstrip(".")
    try:
        # An approved job gives its SIGNED file (with the QR code), exactly as fingerprinted (Stage 7).
        exported = signed_file(job, output, fmt) or export_output(job, output, fmt)
    except ExportError as exc:
        raise HTTPException(409 if output.status != "done" else 400, str(exc))
    how = "Opened" if inline else "Downloaded"
    audit.log("content", "download", f"{how} the {_label(output)} of job #{job.id} as {fmt.upper()}",
              actor=user, target=f"job {job.id}")
    return _file_response(exported, MEDIA_TYPES[fmt], inline)


@router.get("/jobs/{job_id}/kit.zip")
def download_kit(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("operator", "reviewer"))):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, f"Job {job_id} not found.")
    try:
        kit = signed_kit(db, job) or build_kit(job)
    except ExportError as exc:
        raise HTTPException(409, str(exc))
    audit.log("content", "download", f"Downloaded the campaign kit (.zip) of job #{job.id}", actor=user,
              target=f"job {job.id}")
    return _file_response(kit, MEDIA_TYPES["zip"])


def _file_response(exported: ExportedFile, media_type: str, inline: bool = False) -> Response:
    """Send the file's bytes. File names are made by us (job12-advisory.pdf), so they are safe in the header."""
    disposition = "inline" if inline else "attachment"
    return Response(exported.data, media_type=media_type,
                    headers={"Content-Disposition": f'{disposition}; filename="{exported.name}"',
                             "Cache-Control": "no-store"})
