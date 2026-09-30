"""Download routes: real files made from finished outputs (no AI call).

GET /api/jobs/{id}/outputs/{output_id}/download?format=pdf   one file (docx | pdf | pptx | png | srt | txt)
    add &inline=true to show it in the browser instead of saving it (used for the infographic preview)
GET /api/jobs/{id}/kit.zip                                     every finished output of the job in one .zip

Files are saved under data/jobs/<id>/exports/ and made again on each download.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import Job, Output, get_session
from app.exporters import MEDIA_TYPES, ExportError, export_output
from app.exporters.kit import build_kit

router = APIRouter(prefix="/api", tags=["downloads"])


@router.get("/jobs/{job_id}/outputs/{output_id}/download")
def download_output(
    job_id: int,
    output_id: int,
    fmt: Annotated[str, Query(alias="format", description="docx, pdf, pptx, png, srt or txt")],
    inline: bool = False,
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    output = db.get(Output, output_id)
    if job is None or output is None or output.job_id != job_id:
        raise HTTPException(404, f"Output {output_id} of job {job_id} not found.")
    fmt = fmt.lower().lstrip(".")
    try:
        path = export_output(job, output, fmt)
    except ExportError as exc:
        raise HTTPException(409 if output.status != "done" else 400, str(exc))
    return FileResponse(path, media_type=MEDIA_TYPES[fmt], filename=path.name,
                        content_disposition_type="inline" if inline else "attachment")


@router.get("/jobs/{job_id}/kit.zip")
def download_kit(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, f"Job {job_id} not found.")
    try:
        path = build_kit(job)
    except ExportError as exc:
        raise HTTPException(409, str(exc))
    return FileResponse(path, media_type=MEDIA_TYPES["zip"], filename=path.name)
