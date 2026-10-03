"""Stage 6B part 5: encryption at rest. The database cannot be opened without the key, an old plain
database is moved into an encrypted one (keeping a backup), and stored files are AES-256-GCM encrypted."""

import sqlite3

import pytest
try:
    import sqlcipher3
    HAS_SQLCIPHER = True
except (ImportError, Exception):
    import sqlite3 as sqlcipher3
    HAS_SQLCIPHER = False

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app import crypto
from app.config import settings
from app.db import DATABASE_PATH, PLAIN_HEADER, encrypt_plain_database, make_engine
from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

WRONG_KEY = "00" * 32


def test_the_database_file_is_encrypted():
    data = DATABASE_PATH.read_bytes()
    assert not data.startswith(PLAIN_HEADER)
    assert b"CREATE TABLE" not in data and b"audit_log" not in data and b"argon2id" not in data


def test_the_database_cannot_be_opened_without_the_key():
    with pytest.raises(sqlite3.DatabaseError, match="file is not a database"):
        sqlite3.connect(DATABASE_PATH).execute("SELECT count(*) FROM users").fetchone()
    no_key = sqlcipher3.connect(str(DATABASE_PATH))
    with pytest.raises(sqlcipher3.DatabaseError):
        no_key.execute("SELECT count(*) FROM users").fetchone()
    no_key.close()
    with pytest.raises(DatabaseError, match="file is not a database"):
        with make_engine(DATABASE_PATH, WRONG_KEY).connect() as connection:
            connection.execute(text("SELECT count(*) FROM users"))
    # the key the app uses (made from DB_KEY) opens it
    with make_engine(DATABASE_PATH, crypto.database_key_hex()).connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar() >= 0


def test_the_database_key_is_derived_not_db_key_itself():
    import os
    assert crypto.database_key_hex() != os.environ["DB_KEY"]
    assert len(crypto.database_key_hex()) == 64


def _plain_database(path):
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT);
        CREATE TRIGGER no_delete BEFORE DELETE ON notes BEGIN SELECT RAISE(ABORT, 'kept'); END;
    """)
    connection.executemany("INSERT INTO jobs (title) VALUES (?)", [(f"Job {n}",) for n in range(50)])
    connection.execute("INSERT INTO notes (text) VALUES ('secret plan')")
    connection.commit()
    connection.close()


def test_a_plain_database_is_moved_into_an_encrypted_one(tmp_path):
    path = tmp_path / "pramaan.db"
    _plain_database(path)
    key = crypto.database_key_hex()

    backup = encrypt_plain_database(path, key)
    assert backup == tmp_path / "pramaan.db.plain-backup"
    assert backup.read_bytes().startswith(PLAIN_HEADER)  # the old file is kept, unchanged
    assert not path.read_bytes().startswith(PLAIN_HEADER) and b"secret plan" not in path.read_bytes()
    assert not (tmp_path / "pramaan.db.encrypting").exists()

    with make_engine(path, key).connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM jobs")).scalar() == 50
        assert connection.execute(text("SELECT text FROM notes")).scalar() == "secret plan"
        with pytest.raises(DatabaseError, match="kept"):  # triggers are copied too
            connection.execute(text("DELETE FROM notes"))

    assert encrypt_plain_database(path, key) is None  # already encrypted: nothing to do


def test_an_older_backup_is_never_overwritten(tmp_path):
    path = tmp_path / "pramaan.db"
    (tmp_path / "pramaan.db.plain-backup").write_bytes(b"older backup")
    _plain_database(path)
    backup = encrypt_plain_database(path, crypto.database_key_hex())
    assert backup.name.startswith("pramaan.db.plain-backup-")
    assert (tmp_path / "pramaan.db.plain-backup").read_bytes() == b"older backup"


# ---- files ----------------------------------------------------------------------------------------------


def test_files_are_encrypted_with_aes_gcm(tmp_path):
    path = crypto.write_file(tmp_path / "S1-report.txt", b"Aadhaar 2345 6789 0124")
    stored = path.read_bytes()
    assert stored.startswith(crypto.MAGIC) and b"2345" not in stored
    assert crypto.read_file(path) == b"Aadhaar 2345 6789 0124"
    # the same content twice gives different bytes (a new random nonce each time)
    assert crypto.write_file(tmp_path / "again.txt", b"Aadhaar 2345 6789 0124").read_bytes() != stored


def test_changed_or_replaced_files_are_refused(tmp_path):
    path = crypto.write_file(tmp_path / "S1.pages.json", b'{"pages": ["hello"]}')
    changed = bytearray(path.read_bytes())
    changed[-1] ^= 1
    path.write_bytes(bytes(changed))
    with pytest.raises(crypto.DecryptionError, match="changed"):
        crypto.read_file(path)
    path.write_bytes(b'{"pages": ["a planted plain file"]}')
    with pytest.raises(crypto.DecryptionError, match="not encrypted"):
        crypto.read_file(path)


def test_existing_plain_files_are_encrypted_in_place(tmp_path):
    folder = tmp_path / "jobs" / "3" / "sources"
    folder.mkdir(parents=True)
    (folder / "S1-report.pdf").write_bytes(b"%PDF-1.4 plain")
    (folder / "S1.pages.json").write_text('{"pages": ["p1"]}')
    (folder / ".S2.pages.json.part").write_bytes(b"half-written")
    crypto.write_file(folder / "S3.pages.json", b"already encrypted")

    assert crypto.encrypt_existing_files(tmp_path / "jobs") == 2
    assert crypto.read_file(folder / "S1-report.pdf") == b"%PDF-1.4 plain"
    assert crypto.read_file(folder / "S1.pages.json") == b'{"pages": ["p1"]}'
    assert crypto.read_file(folder / "S3.pages.json") == b"already encrypted"
    assert not (folder / ".S2.pages.json.part").exists()
    assert crypto.encrypt_existing_files(tmp_path / "jobs") == 0  # safe to run on every start


def test_every_stored_job_file_is_encrypted():
    client = signed_in_client("operator")
    job = client.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"), "outputs": ["x_thread"]})
    done = wait_for(job.json()["id"])
    client.get(f"/api/jobs/{done['id']}/kit.zip")
    folder = settings.data_dir / "jobs" / str(done["id"])
    files = [p for p in folder.rglob("*") if p.is_file()]
    assert {p.parent.name for p in files} == {"sources", "exports"}
    assert all(p.read_bytes().startswith(crypto.MAGIC) for p in files)
    assert not any(b"ransomware" in p.read_bytes().lower() for p in files)


def test_a_bad_db_key_is_explained_without_showing_it(monkeypatch):
    monkeypatch.setenv("DB_KEY", "not-hex-at-all")
    crypto._master_key.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="64 hexadecimal characters") as error:
            crypto._master_key()
        assert "not-hex-at-all" not in str(error.value)
    finally:
        monkeypatch.undo()
        crypto._master_key.cache_clear()
    assert len(crypto._master_key()) == 32
