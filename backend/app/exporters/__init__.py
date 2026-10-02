"""Exporters: turn a finished output (already saved in the database) into real files.

No AI call is needed: every file is made from the output's JSON, in memory, and made again on every
download, so it always matches the latest output. A copy is kept in data/jobs/<job id>/exports/,
ENCRYPTED (Stage 6B, app/crypto.py): the unencrypted file is never written to disk, it only goes
to the browser.

    advisory, executive_summary  -> .docx and .pdf
    presentation                 -> .pptx
    infographic                  -> .png
    video_package                -> .srt (subtitles), .docx (script and storyboard), .mp4 (video) and
                                    .mp3 (narration, when a voice can read the language; Stage 8)
    linkedin_post, x_thread      -> .txt

Every file is made by one of a few export workers (EXPORT_WORKERS), with a time limit (EXPORT_TIMEOUT_SECONDS,
MEDIA_EXPORT_TIMEOUT_SECONDS for video and narration). A file that is not ready in time gives ExportTimeout,
a clear message, instead of a request that never ends.
"""

import io
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path

from app import crypto
from app.config import settings
from app.exporters.common import ExportInfo, format_date
from app.lang.labels import L
from app.pipeline.output_types import OUTPUT_TYPES

# Formats each output type can be downloaded as (the first is the main one).
FORMATS: dict[str, list[str]] = {
    "advisory": ["pdf", "docx"],
    "executive_summary": ["pdf", "docx"],
    "presentation": ["pptx"],
    "infographic": ["png"],
    "video_package": ["docx", "srt", "mp4"],  # Stage 8: + "mp3" (narration) when the language has a voice
    "linkedin_post": ["txt"],
    "x_thread": ["txt"],
    "sms": ["txt"],  # Stage 8: + "mp3" (the voice announcement) when the language has a voice
}

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "srt": "application/x-subrip",
    "txt": "text/plain; charset=utf-8",
    "zip": "application/zip",
    "mp3": "audio/mpeg",
    "mp4": "video/mp4",
}


def formats_for(output) -> list[str]:
    """The file types this output can be downloaded as. Stage 8: a video package also comes as narration
    (.mp3) when a voice can read its language (app/lang/tts.py)."""
    formats = list(FORMATS.get(output.type, []))
    if output.type in ("video_package", "sms"):
        from app.lang import tts
        if tts.voice_for(output.language) is not None and _voice_wanted(output):
            formats.insert(formats.index("mp4") if "mp4" in formats else len(formats), "mp3")
    return formats


def _voice_wanted(output) -> bool:
    """An emergency alert has a "voice announcement" switch (on by default)."""
    if output.type != "sms":
        return True
    job = getattr(output, "job", None)
    return bool(((job.alert_json if job else None) or {}).get("voice", True))


class ExportError(Exception):
    """The file cannot be made (for example, the output is not finished yet)."""


class ExportTimeout(ExportError):
    """The file was not ready within its time limit (or every export worker was busy)."""


@dataclass
class ExportedFile:
    name: str   # e.g. job12-advisory.pdf
    data: bytes  # the file itself (not encrypted: this is what the person downloads)


def exports_dir(job_id: int) -> Path:
    folder = settings.data_dir / "jobs" / str(job_id) / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_info(job, output) -> ExportInfo:
    from app import branding  # here: branding reads app settings from the database
    return ExportInfo(
        office_name=branding.office_name(),
        logo_png=branding.logo_png(),
        job_id=job.id,
        job_title=job.title,
        date=format_date(job.created_at, output.language),
        tlp=job.tlp,
        output_type=output.type,
        output_label=L(OUTPUT_TYPES[output.type]["label"], output.language),
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
    if fmt not in formats_for(output):
        allowed = ", ".join(formats_for(output)) or "none"
        if fmt == "mp3" and output.type in ("video_package", "sms"):
            from app.lang import tts
            raise ExportError(tts.not_available(output.language) + f" It can be downloaded as: {allowed}.")
        raise ExportError(f"A {OUTPUT_TYPES[output.type]['label']} can be downloaded as: {allowed}.")

    exported = ExportedFile(file_name(job, output, fmt), render(export_info(job, output), output, fmt))
    crypto.write_file(exports_dir(job.id) / exported.name, exported.data)
    return exported


# The export workers. A few threads, shared by every request: downloads, the campaign kit and signing.
_workers = ThreadPoolExecutor(max_workers=settings.export_workers, thread_name_prefix="pramaan-export")


def time_limit(fmt: str) -> float:
    """Seconds a file may take: video and narration read the text aloud first, so they get longer."""
    return settings.media_export_timeout_seconds if fmt in ("mp3", "mp4") else settings.export_timeout_seconds


def render(info: ExportInfo, output, fmt: str) -> bytes:
    """Make the file in memory and return its bytes (never written to disk unencrypted). It is made by an
    export worker; this waits at most time_limit(fmt) seconds for it, then raises ExportTimeout."""
    # Plain values only go to the worker (not the database object, which belongs to this request's session)
    future = _workers.submit(_render_now, info, output.type, output.content_json, fmt)
    limit = time_limit(fmt)
    try:
        return future.result(timeout=limit)
    except FutureTimeout:
        if future.cancel():  # it never started: every worker was busy with other files
            raise ExportTimeout("Pramaan AI is busy making other files. Please try again in a minute.") from None
        # A thread cannot be stopped from outside: it finishes in the background and its result is thrown away.
        raise ExportTimeout(f"Making the {fmt.upper()} file took longer than {limit:g} seconds, so Pramaan AI stopped "
                            "waiting for it. Please try again; if it happens again, tell your Admin.") from None


def _render_now(info: ExportInfo, output_type: str, content: dict, fmt: str) -> bytes:
    buffer = io.BytesIO()
    _writer(output_type, fmt)(info, content, buffer)
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
    if fmt == "mp3" and output_type == "sms":
        from app.exporters.video import write_announcement
        return write_announcement
    if fmt == "mp3":
        from app.exporters.video import write_mp3
        return write_mp3
    if fmt == "mp4":
        from app.exporters.video import write_mp4
        return write_mp4
    from app.exporters.text import write_txt
    return write_txt
