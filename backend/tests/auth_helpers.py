"""Test helpers for accounts.

empty_accounts(): for tests that need "no users yet" (First-time setup). The account tables are
emptied for the test and put back exactly as they were afterwards, so other tests are not affected.
"""

from contextlib import contextmanager

from app.db import Base, SessionLocal, User
from app.auth.passwords import hash_password

# Tables emptied by empty_accounts(), children first (later parts add more, e.g. sessions).
ACCOUNT_TABLES = ["account_requests", "users"]

# A password that follows the rules, used for test accounts (test value only).
TEST_PASSWORD = "correct horse battery staple"


@contextmanager
def empty_accounts():
    tables = [Base.metadata.tables[name] for name in ACCOUNT_TABLES]
    with SessionLocal() as db:
        saved = {t.name: [dict(row._mapping) for row in db.execute(t.select())] for t in tables}
        for table in tables:
            db.execute(table.delete())
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            for table in tables:
                db.execute(table.delete())
            for table in reversed(tables):  # parents first
                if saved[table.name]:
                    db.execute(table.insert(), saved[table.name])
            db.commit()


def make_user(username: str, role: str, password: str = TEST_PASSWORD, full_name: str | None = None,
              **fields) -> User:
    """Add a user straight to the database (or reset it if it exists)."""
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username).one_or_none()
        if user is None:
            user = User(username=username, full_name=full_name or username.replace(".", " ").title(), role=role,
                        password_hash=hash_password(password))
            db.add(user)
        user.role, user.is_active, user.failed_attempts, user.locked_until = role, True, 0, None
        user.password_hash = hash_password(password)
        for name, value in fields.items():
            setattr(user, name, value)
        db.commit()
        return user
