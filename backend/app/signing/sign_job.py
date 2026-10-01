"""Signing a job when a Reviewer approves it (Stage 7).

In this order, while holding the record book lock:
  1. Take the next record number, e.g. PRM-2026-000123.
  2. Make the FINAL files of every output, with a real QR code (verify address + record number) and
     "Approved and signed · Record ..." in the footer. They are saved encrypted under
     data/jobs/<id>/signed/<record number>/ and made read-only: downloads of an approved job always
     give exactly these bytes.
  3. SHA-256 of every final file, and of each output's normalised text (see texts.py).
  4. A manifest (record number, title, TLP, issuing office, approver name and role, time, files and
     fingerprints, text fingerprints) is signed; so is the public version of it (no title or text
     for TLP:RED / AMBER).
  5. A new entry in the record book (hash-chained), the job becomes "approved", one commit.

A later change to the job needs a new version (POST /api/jobs/{id}/new-version), a new review and a
new signature; the new record says which record it replaces.
"""

import dataclasses
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from app import branding, crypto
from app.config import settings
from app.db import Job, Record, User
from app.exporters import FORMATS, ExportedFile, export_info, file_name, render
from app.pipeline.output_types import OUTPUT_TYPES
from app.signing import records
from app.signing.qr import verify_url
from app.signing.signer import ALGORITHM, get_signer
from app.signing.texts import MESSAGE_OUTPUTS, output_texts, text_hash

RESTRICTED_TLP = ("RED", "AMBER")


def signed_dir(job_id: int, record_no: str) -> Path:
    return settings.data_dir / "jobs" / str(job_id) / "signed" / record_no


def is_restricted(tlp: str | None) -> bool:
    """TLP:RED and AMBER (and jobs with no label) publish only the record number, date and fingerprints."""
    return tlp not in ("GREEN", "CLEAR")


def sign_job(db: Session, job: Job, reviewer: User, pin: str = "") -> Record:
    """Sign every finished output of the job and add it to the record book. Commits.
    Raises signer.SigningError if the key or token cannot be used (nothing is changed then)."""
    signer = get_signer(pin)
    key = signer.describe()
    outputs = [o for o in job.outputs if o.status == "done" and o.content_json]

    with records.lock:
        issued_at = records.now_iso()
        record_no = records.next_record_no(db)
        url = verify_url(record_no)
        folder = signed_dir(job.id, record_no)

        files = []
        for output in outputs:
            info = dataclasses.replace(export_info(job, output), record_no=record_no, verify_url=url)
            for fmt in FORMATS.get(output.type, []):
                data = render(info, output, fmt)
                name = file_name(job, output, fmt)
                path = crypto.write_file(folder / name, data)
                os.chmod(path, 0o444)  # signed files are read-only
                files.append({"name": name, "output": output.type, "format": fmt, "bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest()})

        texts = [{"output": o.type, "label": label, "sha256": text_hash(text), "text": text}
                 for o in outputs for label, text in output_texts(o.type, o.content_json)]
        replaces = job.record_no if job.record_no else None

        manifest = {
            "format": records.FORMAT,
            "kind": "issue",
            "record_no": record_no,
            "issued_at": issued_at,
            "job_id": job.id,
            "job_version": job.version,
            "title": job.title,
            "tlp": job.tlp,
            "issuing_office": branding.office_name(),
            "approved_by": {"name": reviewer.full_name, "role": "Reviewer", "user_id": reviewer.id},
            "signer": key,
            "verify_url": url,
            "replaces": replaces,
            "files": files,
            "texts": [{k: t[k] for k in ("output", "label", "sha256")} for t in texts],
        }
        public = public_manifest(manifest, texts)
        manifest_text, public_text = records.canonical(manifest), records.canonical(public)
        entry = Record(
            kind="issue", record_no=record_no, job_id=job.id, job_version=job.version, created_at=issued_at,
            created_by=reviewer.id, manifest=manifest_text, signature=signer.sign(manifest_text.encode("utf-8")),
            public_manifest=public_text, public_signature=signer.sign(public_text.encode("utf-8")),
            key_id=key["key_id"],
        )
        records.append(db, entry)
        job.record_no = record_no
        job.status = "approved"
        db.commit()
    return entry


def public_manifest(manifest: dict, texts: list[dict]) -> dict:
    """What the public verify page may know. TLP:RED / AMBER: only the record number, date and
    fingerprints, marked "restricted". TLP:GREEN / CLEAR: also the title, office, approver ROLE (no
    name), file names, and the text of forwardable messages (X thread, LinkedIn post)."""
    base = {
        "format": manifest["format"],
        "kind": "issue",
        "record_no": manifest["record_no"],
        "issued_at": manifest["issued_at"],
        "replaces": manifest["replaces"],
        "signer": {"key_id": manifest["signer"]["key_id"], "algorithm": ALGORITHM},
    }
    if is_restricted(manifest["tlp"]):
        return base | {
            "restricted": True,
            "files": [{"sha256": f["sha256"]} for f in manifest["files"]],
            "texts": [{"sha256": t["sha256"]} for t in texts],
        }
    return base | {
        "restricted": False,
        "title": manifest["title"],
        "tlp": manifest["tlp"],
        "job_version": manifest["job_version"],
        "issuing_office": manifest["issuing_office"],
        "approved_by": {"role": manifest["approved_by"]["role"]},
        "files": [{k: f[k] for k in ("name", "output", "format", "bytes", "sha256")} for f in manifest["files"]],
        "texts": [
            {"output": t["output"], "label": t["label"], "sha256": t["sha256"]}
            | ({"text": t["text"]} if t["output"] in MESSAGE_OUTPUTS else {})
            for t in texts
        ],
    }


# ---- reading signed files back ----------------------------------------------------------------------


def signed_file(job: Job, output, fmt: str) -> ExportedFile | None:
    """The signed file of an approved job (exactly the bytes that were fingerprinted), or None."""
    if job.status != "approved" or not job.record_no:
        return None
    path = signed_dir(job.id, job.record_no) / file_name(job, output, fmt)
    if not path.exists():
        return None
    return ExportedFile(path.name, crypto.read_file(path))


def signed_kit(db: Session, job: Job, only: set[str] | None = None) -> ExportedFile | None:
    """The campaign kit of an approved job: every signed file, the signed public record and the public
    key (so anyone can check it with no internet), and a README. only: the output types to put in
    (None = all); the record still lists every signed file."""
    entry = records.find_issue(db, job.record_no) if job.status == "approved" and job.record_no else None
    if entry is None:
        return None
    manifest = json.loads(entry.manifest)
    folder = signed_dir(job.id, job.record_no)
    lines = [
        f"Pramaan AI signed kit · Record {entry.record_no}",
        f"Title: {manifest['title']}",
        f"Signed: {manifest['issued_at']} by {manifest['approved_by']['name']} ({manifest['approved_by']['role']})",
        f"Issued by: {manifest['issuing_office']}",
        f"Sharing label: TLP:{manifest['tlp']}" if manifest.get("tlp") else "",
        f"Check it is genuine: {manifest['verify_url']}",
        "",
        "Files (size, SHA-256 fingerprint). Any change to a file changes its fingerprint:",
        *(f"  {f['name']}  {f['bytes']:,} bytes  {f['sha256']}" for f in manifest["files"]),
        "",
        "record.json is the signed public record; public-key.pem checks its signature (ECDSA P-256, SHA-256).",
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "\n".join(line for line in lines if line is not None) + "\n")
        for f in manifest["files"]:
            if only is None or f["output"] in only:
                archive.writestr(f["name"], crypto.read_file(folder / f["name"]))
        archive.writestr("record.json", json.dumps({"manifest": entry.public_manifest,
                                                    "signature": entry.public_signature}, indent=1))
        archive.writestr("public-key.pem", get_signer().public_key_pem())
    return ExportedFile(f"job{job.id}-signed-kit-{entry.record_no}.zip", buffer.getvalue())


def outputs_and_files(job: Job) -> tuple[int, int]:
    """(number of outputs, number of files) that signing would make, for the sign dialog."""
    done = [o for o in job.outputs if o.status == "done" and o.content_json]
    return len(done), sum(len(FORMATS.get(o.type, [])) for o in done)


def labels(job: Job) -> list[str]:
    return [OUTPUT_TYPES[o.type]["label"] for o in job.outputs if o.status == "done"]
