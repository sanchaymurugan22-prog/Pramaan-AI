"""Backups (Stage 9B, design 39): one .zip with everything in data/, made while the app runs.

What goes in:
  pramaan.db   a consistent copy of the database, made with SQLite's own backup (still ENCRYPTED with DB_KEY)
  jobs/ ...    every source, export and signed file (already encrypted on disk, copied as they are)
  branding/, signing keys and anything else in data/ (also encrypted)
Left out: data/backups/ itself, data/watch/ (the operators' own drop folders), old plain-backup files.

The key (DB_KEY in .env) is NOT in the backup: without it the backup cannot be read, so keep a copy of
.env somewhere safe, separately. To restore: stop the app, move data/ away, unzip the backup as the new
data/ folder, put back the .env that belongs to it, start the app.
"""

import os
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import sqlcipher3
    HAS_SQLCIPHER = True
except (ImportError, Exception):
    import sqlite3 as sqlcipher3
    HAS_SQLCIPHER = False

from app import crypto
from app.config import settings
from app.db import DATABASE_PATH

BACKUP_DIR = settings.data_dir / "backups"
NAME = re.compile(r"^pramaan-backup-\d{8}-\d{6}\.zip$")
SKIP_DIRS = {"backups", "watch"}

README = """Pramaan AI backup ({when})

pramaan.db and every file here are ENCRYPTED with DB_KEY from the .env file of the computer that made
this backup. The key is not in this backup. Without it nothing here can be read.

To restore: stop Pramaan AI, move the data/ folder away, unzip this file as the new data/ folder, put back
the .env that belongs to it, and start Pramaan AI again.
"""


def _copy_database(target: Path) -> None:
    """A consistent copy of the live database (SQLite's online backup, page by page)."""
    key = f"\"x'{crypto.database_key_hex()}'\""
    source = sqlcipher3.connect(str(DATABASE_PATH))
    copy = sqlcipher3.connect(str(target))
    try:
        if HAS_SQLCIPHER:
            source.execute(f"PRAGMA key = {key}")
            copy.execute(f"PRAGMA key = {key}")
        source.backup(copy)
        if HAS_SQLCIPHER:
            copy.execute("SELECT count(*) FROM sqlite_master").fetchone()  # it opens with the same key
    finally:
        copy.close()
        source.close()


def make_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    when = datetime.now()
    path = BACKUP_DIR / f"pramaan-backup-{when:%Y%m%d-%H%M%S}.zip"
    partial = path.with_suffix(".partial")
    with tempfile.TemporaryDirectory(dir=BACKUP_DIR) as work:
        db_copy = Path(work) / "pramaan.db"
        _copy_database(db_copy)
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", README.format(when=when.strftime("%d %b %Y, %H:%M")))
            archive.write(db_copy, "pramaan.db")
            for root, dirs, files in os.walk(settings.data_dir):
                relative_root = Path(root).relative_to(settings.data_dir)
                if relative_root == Path("."):
                    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in files:
                    if relative_root == Path(".") and (name.startswith("pramaan.db") or ".plain-backup" in name):
                        continue
                    archive.write(Path(root) / name, (relative_root / name).as_posix())
    os.replace(partial, path)
    return path


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    found = []
    for path in sorted(BACKUP_DIR.glob("pramaan-backup-*.zip"), reverse=True):
        info = path.stat()
        found.append({"name": path.name, "bytes": info.st_size,
                      "created_at": datetime.fromtimestamp(info.st_mtime).astimezone().isoformat()})
    return found


def backup_path(name: str) -> Path | None:
    """The file for a backup name from the list (anything else: None, so no other file can be fetched)."""
    if not NAME.match(name):
        return None
    path = BACKUP_DIR / name
    return path if path.is_file() else None
