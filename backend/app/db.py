"""Database connection and tables: one SQLite file at data/pramaan.db.

Tables so far: jobs, sources, fact_sheets, outputs (Stage 3), output_versions (Stage 5),
safety_decisions (Stage 6A), users and account_requests (Stage 6B). Stage 7 adds records (signing).
`init_db()` creates any missing tables and columns and never deletes data.
SQLCipher encryption is added in Stage 6, here, behind this same module, so nothing else has
to change.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{settings.data_dir / 'pramaan.db'}"

# check_same_thread=False lets FastAPI and the background worker use connections from other threads
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
    owner_id: Mapped[int | None] = mapped_column(default=None)  # linked to users in Stage 6
    # draft | generating | ready | failed | in_review | sent_back | approved
    status: Mapped[str] = mapped_column(String(20), default="draft")
    step: Mapped[str] = mapped_column(String(200), default="")   # what the pipeline is doing now
    error: Mapped[str | None] = mapped_column(Text, default=None)
    tlp: Mapped[str | None] = mapped_column(String(10), default=None)  # RED | AMBER | GREEN | CLEAR, chosen in the Safety check
    # The safety report (app/safety/scanner.py): findings with the operator's choices, indicators,
    # suspicious instructions, suggested TLP. None for jobs made before Stage 6A.
    safety_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    version: Mapped[int] = mapped_column(default=1)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)  # audience, tone, objective, style, detail_level
    quality_score: Mapped[int | None] = mapped_column(default=None)        # 0-100: average of the outputs (Stage 5)
    consistency_json: Mapped[dict | None] = mapped_column(JSON, default=None)  # same numbers in every output? (Stage 5)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    sources: Mapped[list["Source"]] = relationship(back_populates="job", order_by="Source.id")
    fact_sheet: Mapped["FactSheet | None"] = relationship(back_populates="job")
    outputs: Mapped[list["Output"]] = relationship(back_populates="job", order_by="Output.position")
    safety_decisions: Mapped[list["SafetyDecision"]] = relationship(back_populates="job", order_by="SafetyDecision.id")


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
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    output: Mapped[Output] = relationship(back_populates="versions")


class SafetyDecision(Base):
    """One safety decision: who, when, what (a choice for a finding, the TLP label, the scan itself).
    Rows are only added, never changed (see app/safety/decisions.py)."""

    __tablename__ = "safety_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    actor: Mapped[str] = mapped_column(String(100))            # "Operator", "Pramaan (automatic)"
    action: Mapped[str] = mapped_column(String(20))            # scan | choice | instruction | tlp | confirm | start
    item: Mapped[str | None] = mapped_column(String(20), default=None)   # finding id: P1, I2 ...
    value: Mapped[str | None] = mapped_column(String(40), default=None)  # new choice or label
    detail: Mapped[str] = mapped_column(Text)                  # the decision in plain words
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    job: Mapped[Job] = relationship(back_populates="safety_decisions")


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


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite gives times back without a timezone; they are always stored in UTC."""
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def init_db() -> None:
    """Create any tables and columns that don't exist yet (safe to call every time the app starts)."""
    Base.metadata.create_all(engine)
    _add_missing_columns()


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
