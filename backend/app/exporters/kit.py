"""The campaign kit: one .zip with every file of every finished output of a job.

The zip also holds README.txt: the job details, the footer text, and each file's size and
SHA-256 fingerprint (so anyone can check later that a file was not changed).
Outputs blocked by the leak check ("Private data found") are left out, and README.txt says so.
"""

import hashlib
import io
import zipfile

from app import crypto
from app.exporters import FORMATS, ExportedFile, ExportError, export_info, export_output, exports_dir, is_blocked
from app.exporters.common import FOOTER


def build_kit(job) -> ExportedFile:
    done = [o for o in job.outputs if o.status == "done" and o.content_json]
    finished = [o for o in done if not is_blocked(o)]
    blocked = [o for o in done if is_blocked(o)]
    if not finished:
        if blocked:
            raise ExportError("Every finished output has private data in it (see the red warnings), so the kit is empty.")
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
    lines += [f"  {file.name}  {len(file.data):,} bytes  {hashlib.sha256(file.data).hexdigest()}" for file in files]
    if blocked:
        lines += ["", "Left out because private data was found in them:"]
        lines += [f"  {output.type.replace('_', ' ')}" for output in blocked]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "\n".join(lines) + "\n")
        for file in files:
            archive.writestr(file.name, file.data)
    kit = ExportedFile(f"job{job.id}-campaign-kit.zip", buffer.getvalue())
    crypto.write_file(exports_dir(job.id) / kit.name, kit.data)  # encrypted copy
    return kit
