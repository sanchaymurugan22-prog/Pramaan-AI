"""Database connection and tables: one SQLite file at data/pramaan.db.

Tables so far (Stage 3): jobs, sources, fact_sheets, outputs.
Later stages add users (Stage 6), reviews / records / audit_log (Stage 7).
`init_db()` creates any missing tables and never deletes data.
SQLCipher encryption is added in Stage 6, here, behind this same module, so nothing else has
to change.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, String, Text, create_engine
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
    tlp: Mapped[str | None] = mapped_column(String(10), default=None)  # set by the safety check (Stage 6)
    version: Mapped[int] = mapped_column(default=1)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)  # audience, tone, objective, style, detail_level
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    sources: Mapped[list["Source"]] = relationship(back_populates="job", order_by="Source.id")
    fact_sheet: Mapped["FactSheet | None"] = relationship(back_populates="job")
    outputs: Mapped[list["Output"]] = relationship(back_populates="job", order_by="Output.position")


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
    content_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    quality_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    truncated: Mapped[bool] = mapped_column(default=False)
    seconds: Mapped[float | None] = mapped_column(default=None)
    tokens: Mapped[int | None] = mapped_column(default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    job: Mapped[Job] = relationship(back_populates="outputs")


def init_db() -> None:
    """Create any tables that don't exist yet (safe to call every time the app starts)."""
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: gives a route a database session and closes it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
