"""The public verify bundle (Stage 7): the static "Is this real?" site with the latest records.

    verify-page/ (HTML, CSS, JS, fonts)  +  records.json  +  public-key.pem

records.json holds only the PUBLIC part of each record-book entry (public_manifest + its signature),
never the internal manifest, and a signed index listing every entry, so the page notices if an entry
(for example a withdrawal) was left out. No secrets: the page checks everything with the public key.

Used by:
  - the Admin's "Export verify bundle" button: a .zip for one-way (USB) transfer to the public web server
  - scripts/serve-verify.sh: builds data/verify-site/ and serves it on port 8090 for the demo
    (the backend refreshes data/verify-site/ after every signature or withdrawal, if it exists)

Run on its own:  backend/.venv/bin/python -m app.signing.publish [folder]   (default: data/verify-site)
"""

import hashlib
import io
import json
import logging
import shutil
import sys
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import branding
from app.config import PROJECT_ROOT, settings
from app.db import Record, SessionLocal
from app.signing import records
from app.signing.signer import ALGORITHM, get_signer

log = logging.getLogger("pramaan.publish")

VERIFY_PAGE = PROJECT_ROOT / "verify-page"
DEMO_SITE = settings.data_dir / "verify-site"
FORMAT = "pramaan-verify/1"
# Not published: tests, and any old data files lying in the source folder
_SKIP = {"tests", "records.json", "public-key.pem", ".DS_Store", "node_modules"}


def records_json(db: Session) -> bytes:
    signer = get_signer()
    key = signer.describe()
    entries = db.scalars(select(Record).order_by(Record.seq)).all()
    generated_at = records.now_iso()
    index = {
        "format": "pramaan-verify-index/1",
        "generated_at": generated_at,
        "issuer": branding.office_name(),
        "key_id": key["key_id"],
        "count": len(entries),
        "entries": [hashlib.sha256(e.public_manifest.encode("utf-8")).hexdigest() for e in entries],
        "chain_head": entries[-1].entry_hash if entries else records.GENESIS,
    }
    index_text = records.canonical(index)
    data = {
        "format": FORMAT,
        "generated_at": generated_at,
        "issuer": branding.office_name(),
        "key_id": key["key_id"],
        "algorithm": ALGORITHM,
        "index": index_text,
        "index_signature": signer.sign(index_text.encode("utf-8")),
        "entries": [{"seq": e.seq, "kind": e.kind, "record_no": e.record_no, "manifest": e.public_manifest,
                     "signature": e.public_signature} for e in entries],
    }
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


def _site_files() -> list[Path]:
    return sorted(p for p in VERIFY_PAGE.rglob("*")
                  if p.is_file() and not any(part in _SKIP for part in p.relative_to(VERIFY_PAGE).parts))


def build_site(db: Session, target: Path = DEMO_SITE) -> Path:
    """Write the whole site into `target` (made fresh each time)."""
    staging = target.with_name(target.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    for path in _site_files():
        destination = staging / path.relative_to(VERIFY_PAGE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "records.json").write_bytes(records_json(db))
    (staging / "public-key.pem").write_text(get_signer().public_key_pem())
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)
    return target


def bundle_zip(db: Session) -> bytes:
    """The site as a .zip, ready to copy to the public web server."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _site_files():
            archive.write(path, f"verify-site/{path.relative_to(VERIFY_PAGE)}")
        archive.writestr("verify-site/records.json", records_json(db))
        archive.writestr("verify-site/public-key.pem", get_signer().public_key_pem())
        archive.writestr("verify-site/HOW-TO-PUBLISH.txt", (
            "Copy the folder verify-site/ to the public web server, as plain static files (any server works).\n"
            "It contains no secrets. Serve it over HTTPS in production.\n"
            "Records are added by exporting a new bundle from Pramaan AI (Admin -> Record book).\n"))
    return buffer.getvalue()


def refresh_demo_site() -> None:
    """After a signature or withdrawal: update data/verify-site/ if the demo server uses it."""
    if not DEMO_SITE.exists():
        return
    try:
        with SessionLocal() as db:
            build_site(db, DEMO_SITE)
    except Exception:  # never let the demo site stop signing
        log.exception("Could not refresh %s", DEMO_SITE)


if __name__ == "__main__":
    from app.db import init_db

    init_db()
    folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEMO_SITE
    with SessionLocal() as session:
        built = build_site(session, folder)
        count = len(session.scalars(select(Record)).all())
    print(f"Verify site written to {built} ({count} record-book entries).")
