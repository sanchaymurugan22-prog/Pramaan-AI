"""Stage 6B part 7: no password, temporary password, session token or key is ever written to the logs
(Python logging, the console) or to the audit trail, while doing everything that handles them."""

import logging
import os

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import crypto
from app.auth import sessions
from app.config import ensure_secret
from app.db import AuditEntry, Record, SessionLocal, engine
from app.main import app
from tests.auth_helpers import ORIGIN, empty_accounts, signed_in_client

SETUP_PASSWORD = "first setup secret phrase"
REQUEST_PASSWORD = "requested account phrase"
WRONG_PASSWORD = "a wrong guess 12345"
NEW_PASSWORD = "brand new chosen phrase"


def test_no_password_or_key_in_logs_or_audit(tmp_path, monkeypatch, caplog, capsys):
    secrets_seen: list[str] = [SETUP_PASSWORD, REQUEST_PASSWORD, WRONG_PASSWORD, NEW_PASSWORD]
    caplog.set_level(logging.DEBUG)  # everything, from every logger (uvicorn, sqlalchemy, pramaan ...)
    first_row = _last_audit_seq() + 1

    with empty_accounts():
        client = TestClient(app, headers=ORIGIN)
        # first-time setup, sign-in, wrong passwords up to a lock
        assert client.post("/api/auth/setup", json={"username": "log.admin", "full_name": "Log Admin",
                                                    "password": SETUP_PASSWORD}).status_code == 201
        secrets_seen.append(client.cookies.get(sessions.COOKIE_NAME))
        anonymous = TestClient(app, headers=ORIGIN)
        for _ in range(5):
            anonymous.post("/api/auth/login", json={"username": "log.admin", "password": WRONG_PASSWORD})
        anonymous.post("/api/auth/login", json={"username": WRONG_PASSWORD, "password": WRONG_PASSWORD})
        # access request with a password, a new user and a reset (temporary passwords)
        anonymous.post("/api/auth/request-access", json={"username": "log.requester", "full_name": "Log Requester",
                                                         "role": "operator", "reason": "Testing the logs",
                                                         "password": REQUEST_PASSWORD})
        made = client.post("/api/admin/users", json={"username": "log.user", "full_name": "Log User", "role": "reviewer"})
        secrets_seen.append(made.json()["temporary_password"])
        reset = client.post(f"/api/admin/users/{made.json()['user']['id']}/reset-password")
        secrets_seen.append(reset.json()["temporary_password"])
        temp_client = TestClient(app, headers=ORIGIN)
        temp_client.post("/api/auth/login", json={"username": "log.user", "password": secrets_seen[-1]})
        secrets_seen.append(temp_client.cookies.get(sessions.COOKIE_NAME))
        client.post("/api/auth/change-password", json={"current_password": SETUP_PASSWORD,
                                                       "new_password": NEW_PASSWORD})
        client.post("/api/auth/logout")

    # a secret made on first run
    env_file = tmp_path / ".env"
    env_file.write_text("DB_KEY=\n")
    monkeypatch.delenv("LOG_TEST_KEY", raising=False)
    secrets_seen.append(ensure_secret("LOG_TEST_KEY", env_file))
    monkeypatch.delenv("LOG_TEST_KEY")

    # and the keys the app runs with
    secrets_seen += [os.environ["DB_KEY"], os.environ["APP_SECRET_KEY"], crypto.database_key_hex()]
    assert crypto.database_key_hex() not in str(engine.url) and crypto.database_key_hex() not in repr(engine)

    captured = capsys.readouterr()
    written = "\n".join([caplog.text, captured.out, captured.err, _audit_text(first_row)])
    assert "Failed sign-in" in written and "Account locked" in written  # the events ARE logged ...
    for secret in secrets_seen:
        assert secret and secret not in written  # ... but never a password, token or key


def _last_audit_seq() -> int:
    with SessionLocal() as db:
        return db.scalar(select(AuditEntry.seq).order_by(AuditEntry.seq.desc()).limit(1)) or 0


def _audit_text(first_row: int) -> str:
    with SessionLocal() as db:
        rows = db.scalars(select(AuditEntry).where(AuditEntry.seq >= first_row))
        return "\n".join(f"{r.actor} {r.action} {r.target} {r.detail}" for r in rows)


def test_signed_in_clients_still_work_after_the_accounts_were_put_back():
    """empty_accounts() above must leave the other tests' users and sessions as they were."""
    assert signed_in_client("operator").get("/api/jobs").status_code == 200


def test_signing_never_logs_the_private_key(caplog, capsys):
    """Stage 7: approving signs with the private key; it never appears in logs, the audit trail, records,
    the published bundle or any answer."""
    from app.signing import publish
    from app.signing.signer import get_signer
    from tests.test_signing import approved_job

    caplog.set_level(logging.DEBUG)
    first_row = _last_audit_seq() + 1
    job = approved_job(outputs=("x_thread",))
    signer = get_signer()
    pem = crypto.read_file(signer._private_path).decode()  # the test key, read only to compare
    key_body = "".join(pem.strip().splitlines()[1:-1])
    assert len(key_body) > 100

    with SessionLocal() as db:
        bundle = publish.records_json(db).decode()
        stored_records = " ".join(f"{r.manifest} {r.public_manifest}" for r in db.query(Record))
    admin = signed_in_client("admin", "log.key.admin")
    answers = admin.get("/api/records").text + admin.get(f"/api/records/{job['record']['record_no']}").text
    captured = capsys.readouterr()
    written = "\n".join([caplog.text, captured.out, captured.err, _audit_text(first_row), bundle, stored_records, answers])
    for piece in (key_body, key_body[:40], key_body[-40:]):
        assert piece not in written
    assert "PRIVATE KEY" not in written
