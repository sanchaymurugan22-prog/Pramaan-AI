"""Database connection and tables: one ENCRYPTED SQLite file at data/pramaan.db (SQLCipher, Stage 6B).

Tables so far: jobs, sources, fact_sheets, outputs (Stage 3), output_versions (Stage 5),
safety_decisions (Stage 6A), users, account_requests, sessions, reviews, audit_log (Stage 6B),
records (Stage 7: the record book of signed documents), notifications, watch_settings, watch_files (Stage 9A).
`init_db()` first encrypts a database left from before Stage 6B (keeping the old plain file as
data/pramaan.db.plain-backup), then creates any missing tables and columns. It never deletes data.
The rest of the app only uses `engine` / `SessionLocal` and does not know about the encryption.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import sqlcipher3
from sqlalchemy import JSON, ForeignKey, String, Text, create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import QueuePool

from app import crypto
from app.config import settings

log = logging.getLogger("pramaan.db")

settings.data_dir.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = settings.data_dir / "pramaan.db"
PLAIN_HEADER = b"SQLite format 3\x00"  # the first 16 bytes of every UNencrypted SQLite file


def make_engine(path: Path, key_hex: str):
    """An SQLAlchemy engine for an SQLCipher file. The key is sent as the first statement on every new
    connection ("PRAGMA key"); SQLAlchemy never prints it (it shows the password in a URL as ***).
    A raw 256-bit key (x'...') is used, so no slow passphrase stretching is needed on each connection."""
    url = URL.create("sqlite+pysqlcipher", password=f"x'{key_hex}'", database=str(path))
    # check_same_thread=False lets FastAPI and the background worker use connections from other threads.
    # QueuePool (as for plain SQLite files) instead of the SQLCipher default of one connection per thread.
    return create_engine(url, connect_args={"check_same_thread": False}, poolclass=QueuePool)


engine = make_engine(DATABASE_PATH, crypto.database_key_hex())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """All database models inherit from this."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    """One transformation: some sources in, several outputs out."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[int | None] = mapped_column(default=None)  # the Operator who created it (None: before Stage 6B)
    # draft | generating | ready | failed | in_review | sent_back | approved
    status: Mapped[str] = mapped_column(String(20), default="draft")
    step: Mapped[str] = mapped_column(String(200), default="")   # what the pipeline is doing now
    error: Mapped[str | None] = mapped_column(Text, default=None)
    tlp: Mapped[str | None] = mapped_column(String(10), default=None)  # RED | AMBER | GREEN | CLEAR, chosen in the Safety check
    # The safety report (app/safety/scanner.py): findings with the operator's choices, indicators,
    # suspicious instructions, suggested TLP. None for jobs made before Stage 6A.
    safety_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    version: Mapped[int] = mapped_column(default=1)
    record_no: Mapped[str | None] = mapped_column(String(20), default=None)  # latest signed record (Stage 7)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)  # audience, tone, objective, style, detail_level
    quality_score: Mapped[int | None] = mapped_column(default=None)        # 0-100: average of the outputs (Stage 5)
    consistency_json: Mapped[dict | None] = mapped_column(JSON, default=None)  # same numbers in every output? (Stage 5)
    # Stage 9A: which AI wrote it (mock | local | cloud, set when the AI starts; None = not started / before 9A)
    ai_mode: Mapped[str | None] = mapped_column(String(10), default=None)
    # how the job was made: manual (New transformation) | watch (Watch folder) | emergency (Emergency alert)
    created_via: Mapped[str] = mapped_column(String(20), default="manual")
    # Watch folder: the outputs ticked in advance on step 3 ("kit to prepare"); None = the usual defaults
    suggested_outputs: Mapped[list | None] = mapped_column(JSON, default=None)
    # Emergency alert: the alert form ({type, severity, area, message}); reviewers see these jobs first
    alert_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    sources: Mapped[list["Source"]] = relationship(back_populates="job", order_by="Source.id")
    fact_sheet: Mapped["FactSheet | None"] = relationship(back_populates="job")
    outputs: Mapped[list["Output"]] = relationship(back_populates="job", order_by="Output.position")
    safety_decisions: Mapped[list["SafetyDecision"]] = relationship(back_populates="job", order_by="SafetyDecision.id")
    reviews: Mapped[list["Review"]] = relationship(back_populates="job", order_by="Review.id")
    # owner_id has no database-level foreign key (the column is older than the users table)
    owner: Mapped["User | None"] = relationship(primaryjoin="foreign(Job.owner_id) == User.id", viewonly=True)


class Source(Base):
    """One input: pasted text or an uploaded file."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(10))  # "S1", "S2", ... as used in the fact sheet
    filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20))        # text | txt | pdf | docx
    sha256: Mapped[str] = mapped_column(String(64))
    text_path: Mapped[str] = mapped_column(String(500))  # the extracted pages (JSON file under data/)
    pages: Mapped[int]
    chars: Mapped[int]

    job: Mapped[Job] = relationship(back_populates="sources")


class FactSheet(Base):
    """The ONE fact sheet built from a job's sources. Every output is written from it."""

    __tablename__ = "fact_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    job: Mapped[Job] = relationship(back_populates="fact_sheet")


class Output(Base):
    """One generated output (advisory, X thread, ...) for a job."""

    __tablename__ = "outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    language: Mapped[str] = mapped_column(String(10), default="en")
    position: Mapped[int] = mapped_column(default=0)  # generation order: short outputs first
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | generating | done | failed
    content_json: Mapped[dict | None] = mapped_column(JSON, default=None)  # always the LATEST version
    quality_json: Mapped[dict | None] = mapped_column(JSON, default=None)  # checks of the latest version
    quality_score: Mapped[int | None] = mapped_column(default=None)         # 0-100
    version: Mapped[int] = mapped_column(default=0)                         # 0 = nothing written yet
    origin: Mapped[str] = mapped_column(String(20), default="ai")           # latest version: ai | human | regenerated
    error: Mapped[str | None] = mapped_column(Text, default=None)
    truncated: Mapped[bool] = mapped_column(default=False)
    seconds: Mapped[float | None] = mapped_column(default=None)
    tokens: Mapped[int | None] = mapped_column(default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    job: Mapped[Job] = relationship(back_populates="outputs")
    versions: Mapped[list["OutputVersion"]] = relationship(back_populates="output", order_by="OutputVersion.version")


class OutputVersion(Base):
    """Every version of an output: as the AI wrote it, each human edit, each regeneration.
    Old versions are never changed or deleted, so a reviewer can always see what changed."""

    __tablename__ = "output_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    output_id: Mapped[int] = mapped_column(ForeignKey("outputs.id"), index=True)
    version: Mapped[int]                                   # 1, 2, 3 ...
    origin: Mapped[str] = mapped_column(String(20))        # ai | human | regenerated
    content_json: Mapped[dict] = mapped_column(JSON)
    quality_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    quality_score: Mapped[int | None] = mapped_column(default=None)
    # human: who edited it; regenerated: who asked for it; ai: who started the job (None before Stage 6B)
    created_by: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    output: Mapped[Output] = relationship(back_populates="versions")


class SafetyDecision(Base):
    """One safety decision: who, when, what (a choice for a finding, the TLP label, the scan itself).
    Rows are only added, never changed (see app/safety/decisions.py)."""

    __tablename__ = "safety_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    actor: Mapped[str] = mapped_column(String(100))            # the person's full name, or "Pramaan (automatic)"
    user_id: Mapped[int | None] = mapped_column(default=None)  # None = automatic (or made before Stage 6B)
    action: Mapped[str] = mapped_column(String(20))            # scan | choice | instruction | tlp | confirm | start
    item: Mapped[str | None] = mapped_column(String(20), default=None)   # finding id: P1, I2 ...
    value: Mapped[str | None] = mapped_column(String(40), default=None)  # new choice or label
    detail: Mapped[str] = mapped_column(Text)                  # the decision in plain words
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    job: Mapped[Job] = relationship(back_populates="safety_decisions")


class Review(Base):
    """The review history of a job (Stage 6B): submitted by an Operator, then approved or sent back
    (with notes) by a Reviewer. Rows are only added, never changed."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))       # submitted | approved | sent_back | reopened
    notes: Mapped[str] = mapped_column(Text, default="")
    job_version: Mapped[int] = mapped_column(default=1)     # the job's version at the time
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    job: Mapped[Job] = relationship(back_populates="reviews")
    user: Mapped["User"] = relationship()


class Record(Base):
    """The record book (Stage 7): one row per signed document set ("issue") or withdrawal ("withdraw").
    Append-only and hash-chained like the audit trail (see app/signing/records.py).

    manifest / signature: the full signed description (title, office, approver, every file and text
    fingerprint), kept here. public_manifest / public_signature: what is published on the verify page
    (for TLP:RED / AMBER without the title or any text)."""

    __tablename__ = "records"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)  # 1, 2, 3 ... no gaps
    kind: Mapped[str] = mapped_column(String(10))                 # issue | withdraw
    record_no: Mapped[str] = mapped_column(String(20), index=True)  # PRM-2026-000123 (withdraw: the record withdrawn)
    job_id: Mapped[int | None] = mapped_column(default=None)
    job_version: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[str] = mapped_column(String(40))           # ISO text in UTC, as signed
    created_by: Mapped[int | None] = mapped_column(default=None)  # the Reviewer who signed / the Admin who withdrew
    manifest: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(Text)
    public_manifest: Mapped[str] = mapped_column(Text)
    public_signature: Mapped[str] = mapped_column(Text)
    key_id: Mapped[str] = mapped_column(String(16))
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64))


class Notification(Base):
    """An in-app notification for one person (Stage 9A): a job finished, was sent back, approved,
    signed, submitted for review, or the watch folder drafted a file. Nothing is ever sent outside the app."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # finished | failed | sent_back | approved | signed | submitted | watch | alert
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    job_id: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    read_at: Mapped[datetime | None] = mapped_column(default=None)


class WatchSettings(Base):
    """One Operator's watch folder (Stage 9A): a folder inside data/watch/ that is checked every minute.
    New .txt / .pdf / .docx files there become DRAFT jobs that wait at the Safety check."""

    __tablename__ = "watch_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    folder: Mapped[str] = mapped_column(String(200), default="")         # relative to data/watch/, e.g. "incoming"
    outputs: Mapped[list] = mapped_column(JSON, default=list)            # the kit ticked in advance on step 3
    skip_duplicates: Mapped[bool] = mapped_column(default=True)          # same file as an earlier job -> skipped
    notify: Mapped[bool] = mapped_column(default=True)                   # in-app notification for each draft
    last_check: Mapped[datetime | None] = mapped_column(default=None)


class WatchFile(Base):
    """Every file the watch folder has seen, so each one is handled once (Stage 9A)."""

    __tablename__ = "watch_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    folder: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    size: Mapped[int]
    mtime: Mapped[float]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))   # drafted | skipped | failed
    detail: Mapped[str] = mapped_column(Text, default="")
    job_id: Mapped[int | None] = mapped_column(default=None)
    found_at: Mapped[datetime] = mapped_column(default=utc_now)


class User(Base):
    """A person who can sign in (Stage 6B). There are no built-in accounts: the first Admin is made on
    the First-time setup screen, everyone else by an Admin (or by an approved access request)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # always lower case
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))              # operator | reviewer | admin
    password_hash: Mapped[str] = mapped_column(String(200))    # argon2id, never the password itself
    is_active: Mapped[bool] = mapped_column(default=True)      # False = switched off by an Admin
    must_change_password: Mapped[bool] = mapped_column(default=False)  # True after an Admin set a temporary one
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    last_login: Mapped[datetime | None] = mapped_column(default=None)
    failed_attempts: Mapped[int] = mapped_column(default=0)   # wrong passwords in a row
    locked_until: Mapped[datetime | None] = mapped_column(default=None)


class AccountRequest(Base):
    """Something only an Admin can do for you, asked from the sign-in pages (no email: works offline).
    kind = access: "Request access" (a new account; the password is chosen now, stored only as a hash)
    kind = reset:  "Forgot password" (the Admin sets a temporary password)"""

    __tablename__ = "account_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))              # access | reset
    username: Mapped[str] = mapped_column(String(40), index=True)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str | None] = mapped_column(String(20), default=None)   # access: operator | reviewer
    reason: Mapped[str] = mapped_column(Text, default="")                # why / message to the Admin
    password_hash: Mapped[str | None] = mapped_column(String(200), default=None)  # access only
    status: Mapped[str] = mapped_column(String(10), default="pending")   # pending | approved | rejected | done
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)


class UserSession(Base):
    """One sign-in (Stage 6B). The browser holds a random token in a cookie; only an HMAC fingerprint of
    it is stored here, so a copy of the database cannot be used to sign in. Signing out deletes the row."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped[User] = relationship()


class AuditEntry(Base):
    """One line of the audit trail (Stage 6B): who did what, and when. Append-only and hash-chained
    (see app/audit.py): each row stores the SHA-256 of the row before it, and its own SHA-256 over that
    plus its content, so changing or deleting any row breaks the chain from that row on."""

    __tablename__ = "audit_log"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)  # 1, 2, 3 ... no gaps
    created_at: Mapped[str] = mapped_column(String(40))       # ISO text in UTC, hashed exactly as stored
    actor_id: Mapped[int | None] = mapped_column(default=None)  # None = the system, or someone not signed in
    actor: Mapped[str] = mapped_column(String(100))           # name at the time: "Priya Sharma", "System"
    category: Mapped[str] = mapped_column(String(20), index=True)  # security | users | content | review | system
    action: Mapped[str] = mapped_column(String(40))           # short code, e.g. sign_in, job_created, approved
    target: Mapped[str] = mapped_column(String(100), default="")   # e.g. "job 12", "user priya.sharma"
    detail: Mapped[str] = mapped_column(Text, default="")     # plain words; never a password or key
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64))


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite gives times back without a timezone; they are always stored in UTC."""
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def init_db() -> None:
    """Encrypt anything left from before Stage 6B, then create any tables and columns that don't exist yet
    (safe to call every time the app starts)."""
    encrypt_plain_database(DATABASE_PATH, crypto.database_key_hex())
    crypto.encrypt_existing_files(settings.data_dir / "jobs")
    try:
        Base.metadata.create_all(engine)
    except DatabaseError as exc:
        if "file is not a database" in str(exc):
            raise RuntimeError(
                f"{DATABASE_PATH} cannot be opened with DB_KEY from .env: the key is wrong, or the file is "
                "damaged. Put back the .env that belongs to this data folder."
            ) from None
        raise
    _add_missing_columns()
    protect_audit_log()
    protect_append_only("records", "The record book is append-only")


def encrypt_plain_database(path: Path, key_hex: str) -> Path | None:
    """If `path` is a plain (unencrypted) SQLite file, make an encrypted copy with SQLCipher, check that
    every table has the same number of rows, then swap them. The plain file is kept next to it as
    <name>.plain-backup (delete it yourself after checking). Returns the backup's path, or None if there
    was nothing to do."""
    if not path.exists():
        return None
    with path.open("rb") as file:
        if file.read(16) != PLAIN_HEADER:
            return None  # already encrypted

    encrypted = path.with_name(path.name + ".encrypting")
    encrypted.unlink(missing_ok=True)  # left over from a start that stopped half-way
    plain = sqlcipher3.connect(str(path))  # no key given: SQLCipher reads it as a normal SQLite file
    try:
        plain.execute(f"ATTACH DATABASE ? AS encrypted KEY \"x'{key_hex}'\"", (str(encrypted),))
        plain.execute("SELECT sqlcipher_export('encrypted')")  # copies every table, index, trigger and row
        plain.execute("DETACH DATABASE encrypted")
        tables = [row[0] for row in plain.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        counts = {t: plain.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        plain.close()

    check = sqlcipher3.connect(str(encrypted))
    try:
        check.execute(f"PRAGMA key = \"x'{key_hex}'\"")
        copied = {t: check.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        check.close()
    if copied != counts:
        encrypted.unlink()
        raise RuntimeError("Encrypting the database did not copy every row; nothing was changed.")

    backup = path.with_name(path.name + ".plain-backup")
    if backup.exists():  # never overwrite an older backup
        backup = path.with_name(f"{path.name}.plain-backup-{datetime.now():%Y%m%d-%H%M%S}")
    os.replace(path, backup)
    os.replace(encrypted, path)
    log.warning("Encrypted the database (%d tables, %d rows). The old UNENCRYPTED copy is %s: delete it after "
                "checking that the app works.", len(tables), sum(counts.values()), backup)
    return backup


def protect_audit_log() -> None:
    """The database itself refuses to change or delete audit rows (defence in depth: someone with the
    key could still drop these rules, and then the hash chain shows what they changed)."""
    protect_append_only("audit_log", "The audit trail is append-only")


def protect_append_only(table: str, message: str) -> None:
    """Triggers that make the database refuse UPDATE and DELETE on a table."""
    with engine.begin() as connection:
        for change in ("UPDATE", "DELETE"):
            connection.execute(text(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{change.lower()} BEFORE {change} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{message}'); END"
            ))


def _add_missing_columns() -> None:
    """create_all() makes new tables but does not add new columns to old tables. A database made by an
    earlier stage gets them here (existing rows get the column's default), so no data is lost."""
    existing = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            have = {column["name"] for column in existing.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                default = column.default.arg if column.default is not None and column.default.is_scalar else None
                sql = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
                if isinstance(default, bool):
                    sql += f" DEFAULT {int(default)}"
                elif isinstance(default, (int, float)):
                    sql += f" DEFAULT {default}"
                elif isinstance(default, str):
                    sql += " DEFAULT '" + default.replace("'", "''") + "'"
                connection.execute(text(sql))


def get_session():
    """FastAPI dependency: gives a route a database session and closes it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
