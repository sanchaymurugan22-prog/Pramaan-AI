"""The campaign kit: one .zip with every file of every finished output of a job.

The zip also holds README.txt: the job details, the footer text, and each file's size and
SHA-256 fingerprint (so anyone can check later that a file was not changed).
"""

import hashlib
import os
import zipfile
from pathlib import Path

from app.exporters import FORMATS, ExportError, export_info, export_output, exports_dir
from app.exporters.common import FOOTER


def build_kit(job) -> Path:
    finished = [o for o in job.outputs if o.status == "done" and o.content_json]
    if not finished:
        raise ExportError("No outputs are finished yet, so there is nothing to put in the kit.")

    files = [export_output(job, output, fmt) for output in finished for fmt in FORMATS[output.type]]
    info = export_info(job, finished[0])

    lines = [
        f"Pramaan AI campaign kit · Job #{job.id}",
        f"Title: {job.title}",
        f"Prepared: {info.date}",
    ]
    if info.tlp_label:
        lines.append(f"Sharing label: {info.tlp_label}")
    lines += [FOOTER, "QR codes are added when a reviewer signs the files.", "", "Files (size, SHA-256 fingerprint):"]
    lines += [f"  {path.name}  {path.stat().st_size:,} bytes  {_sha256(path)}" for path in files]

    path = exports_dir(job.id) / f"job{job.id}-campaign-kit.zip"
    temporary = path.with_name(f".{path.name}.part")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "\n".join(lines) + "\n")
        for file in files:
            archive.write(file, arcname=file.name)
    os.replace(temporary, path)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
