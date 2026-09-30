"""Exporters: turn a finished output (already saved in the database) into real files.

No AI call is needed: every file is made from the output's JSON. Files are written to
data/jobs/<job id>/exports/ and made again on every download, so they always match the
latest output.

    advisory, executive_summary  -> .docx and .pdf
    presentation                 -> .pptx
    infographic                  -> .png
    video_package                -> .srt (subtitles) and .docx (script and storyboard)
    linkedin_post, x_thread      -> .txt
"""

import os
from pathlib import Path

from app.config import settings
from app.exporters.common import ExportInfo, format_date
from app.pipeline.output_types import OUTPUT_TYPES

# Formats each output type can be downloaded as (the first is the main one).
FORMATS: dict[str, list[str]] = {
    "advisory": ["pdf", "docx"],
    "executive_summary": ["pdf", "docx"],
    "presentation": ["pptx"],
    "infographic": ["png"],
    "video_package": ["docx", "srt"],
    "linkedin_post": ["txt"],
    "x_thread": ["txt"],
}

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "srt": "application/x-subrip",
    "txt": "text/plain; charset=utf-8",
    "zip": "application/zip",
}


class ExportError(Exception):
    """The file cannot be made (for example, the output is not finished yet)."""


def exports_dir(job_id: int) -> Path:
    folder = settings.data_dir / "jobs" / str(job_id) / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_info(job, output) -> ExportInfo:
    return ExportInfo(
        job_id=job.id,
        job_title=job.title,
        date=format_date(job.created_at),
        tlp=job.tlp,
        output_type=output.type,
        output_label=OUTPUT_TYPES[output.type]["label"],
        language=output.language,
    )


def file_name(job, output, fmt: str) -> str:
    """e.g. job12-advisory.pdf (the language is added for non-English outputs: job12-advisory-hi.pdf)."""
    language = "" if output.language == "en" else f"-{output.language}"
    return f"job{job.id}-{output.type.replace('_', '-')}{language}.{fmt}"


def export_output(job, output, fmt: str) -> Path:
    """Make one file for one output and return its path."""
    if output.status != "done" or not output.content_json:
        raise ExportError("This output is not finished yet.")
    if is_blocked(output):
        raise ExportError("Private data found in this output (see the red warning). Edit the hidden values out, "
                          "then download it.")
    if fmt not in FORMATS.get(output.type, []):
        allowed = ", ".join(FORMATS.get(output.type, [])) or "none"
        raise ExportError(f"A {OUTPUT_TYPES[output.type]['label']} can be downloaded as: {allowed}.")

    writer = _writer(output.type, fmt)
    path = exports_dir(job.id) / file_name(job, output, fmt)
    # Write to a temporary name first, so a half-written file is never served.
    temporary = path.with_name(f".{path.name}.part")
    writer(export_info(job, output), output.content_json, temporary)
    os.replace(temporary, path)
    return path


def is_blocked(output) -> bool:
    """True when the leak check found a hidden value in the output (Stage 6A)."""
    return bool((output.quality_json or {}).get("leaks"))


def _writer(output_type: str, fmt: str):
    # Imported here so starting the app does not load every document library.
    if fmt == "pdf":
        from app.exporters.pdf import write_pdf
        return write_pdf
    if fmt == "docx":
        from app.exporters.docx import write_docx
        return write_docx
    if fmt == "pptx":
        from app.exporters.pptx import write_pptx
        return write_pptx
    if fmt == "png":
        from app.exporters.infographic import write_png
        return write_png
    if fmt == "srt":
        from app.exporters.srt import write_srt
        return write_srt
    from app.exporters.text import write_txt
    return write_txt
