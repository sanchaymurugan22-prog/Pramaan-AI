"""Database connection: one SQLite file at data/pramaan.db.

Stage 2 only sets up the engine and session. Tables (users, jobs, sources, ...)
are added from Stage 3. SQLCipher encryption is added in Stage 6, here, behind
this same module, so nothing else has to change.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{settings.data_dir / 'pramaan.db'}"

# check_same_thread=False lets FastAPI use the connection from its worker threads
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """All database models inherit from this."""


def get_session():
    """FastAPI dependency: gives a route a database session and closes it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
