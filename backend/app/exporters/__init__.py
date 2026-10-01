"""Exporters: turn a finished output (already saved in the database) into real files.

No AI call is needed: every file is made from the output's JSON, in memory, and made again on every
download, so it always matches the latest output. A copy is kept in data/jobs/<job id>/exports/,
ENCRYPTED (Stage 6B, app/crypto.py): the unencrypted file is never written to disk, it only goes
to the browser.

    advisory, executive_summary  -> .docx and .pdf
    presentation                 -> .pptx
    infographic                  -> .png
    video_package                -> .srt (subtitles) and .docx (script and storyboard)
    linkedin_post, x_thread      -> .txt
"""

import io
from dataclasses import dataclass
from pathlib import Path

from app import crypto
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


@dataclass
class ExportedFile:
    name: str   # e.g. job12-advisory.pdf
    data: bytes  # the file itself (not encrypted: this is what the person downloads)


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


def export_output(job, output, fmt: str) -> ExportedFile:
    """Make one file for one output. An encrypted copy is saved under exports/."""
    if output.status != "done" or not output.content_json:
        raise ExportError("This output is not finished yet.")
    if is_blocked(output):
        raise ExportError("Private data found in this output (see the red warning). Edit the hidden values out, "
                          "then download it.")
    if fmt not in FORMATS.get(output.type, []):
        allowed = ", ".join(FORMATS.get(output.type, [])) or "none"
        raise ExportError(f"A {OUTPUT_TYPES[output.type]['label']} can be downloaded as: {allowed}.")

    exported = ExportedFile(file_name(job, output, fmt), render(export_info(job, output), output, fmt))
    crypto.write_file(exports_dir(job.id) / exported.name, exported.data)
    return exported


def render(info: ExportInfo, output, fmt: str) -> bytes:
    """Make the file in memory and return its bytes (never written to disk unencrypted)."""
    buffer = io.BytesIO()
    _writer(output.type, fmt)(info, output.content_json, buffer)
    return buffer.getvalue()


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
