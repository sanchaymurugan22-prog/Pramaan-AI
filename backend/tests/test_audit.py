"""Stage 6B part 4: the audit trail. What is logged, the Admin screen's filters, and the hash chain:
append-only in the database, and "Verify chain" finds the first row that was changed or deleted."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app import audit
from app.db import AuditEntry, SessionLocal, engine, protect_audit_log
from app.main import app
from tests.auth_helpers import ORIGIN, TEST_PASSWORD, make_user, signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

admin = signed_in_client("admin", "audit.admin")


def entries(**filters) -> list[dict]:
    return admin.get("/api/admin/audit", params={"limit": 200, **filters}).json()["entries"]


def test_everything_listed_is_logged():
    operator = signed_in_client("operator", "audit.operator")
    reviewer = signed_in_client("reviewer", "audit.reviewer")
    anonymous = TestClient(app, headers=ORIGIN)

    # sign-in, failed sign-in, lockout
    make_user("audit.locked", "operator")
    for _ in range(5):
        anonymous.post("/api/auth/login", json={"username": "audit.locked", "password": "not the password"})
    anonymous.post("/api/auth/login", json={"username": "audit.locked", "password": TEST_PASSWORD})
    signed = TestClient(app, headers=ORIGIN)
    signed.post("/api/auth/login", json={"username": "audit.operator", "password": TEST_PASSWORD})

    # a job from start to approval, with safety choices, an edit, a regenerate, downloads, send back
    job = operator.post("/api/jobs", files={"files": ("report.txt", SAMPLE_REPORT.read_bytes(), "text/plain")}).json()
    url = f"/api/jobs/{job['id']}"
    operator.put(f"{url}/safety", json={"tlp": "GREEN"})
    operator.post(f"{url}/start", json={"outputs": ["x_thread"]})
    done = wait_for(job["id"])
    output = done["outputs"][0]
    operator.put(f"{url}/outputs/{output['id']}", json={"fields": [{"path": ["tweets", 0, "text"], "text": "Patch now."}]})
    operator.post(f"{url}/outputs/{output['id']}/regenerate")
    wait_for(job["id"])
    operator.get(f"{url}/outputs/{output['id']}/download?format=txt")
    operator.get(f"{url}/kit.zip")
    operator.post(f"{url}/submit", json={})
    reviewer.post(f"{url}/review", json={"decision": "send_back", "notes": "Shorter please."})
    operator.post(f"{url}/submit", json={})
    reviewer.post(f"{url}/review", json={"decision": "approve"})

    # user changes, then sign-out
    made = admin.post("/api/admin/users", json={"username": "audit.new", "full_name": "Audit New", "role": "operator"})
    admin.put(f"/api/admin/users/{made.json()['user']['id']}", json={"role": "reviewer"})
    admin.post(f"/api/admin/users/{made.json()['user']['id']}/reset-password")
    signed.post("/api/auth/logout")

    logged = entries()
    actions = {e["action"] for e in logged}
    for expected in ("sign_in", "sign_in_failed", "locked", "sign_out", "job_created", "safety_scan", "safety_tlp",
                     "safety_confirm", "safety_start", "generated", "output_edited", "output_regenerate", "download",
                     "submitted", "sent_back", "approved", "user_created", "user_changed", "password_reset"):
        assert expected in actions, expected

    about_job = [e for e in logged if e["target"] == f"job {job['id']}"]
    by_action = {e["action"]: e for e in about_job}
    assert by_action["job_created"]["actor"] == "Audit Operator"
    assert by_action["safety_scan"]["actor"] == "System"
    assert by_action["sent_back"]["detail"] == f"Sent back job #{job['id']} v1 with notes: “Shorter please.”"
    assert by_action["approved"]["actor"] == "Audit Reviewer" and "v2" in by_action["approved"]["detail"]
    locks = [e for e in logged if e["target"] == "user audit.locked"]
    assert [e["action"] for e in reversed(locks)] == ["sign_in_failed"] * 4 + ["locked", "sign_in_failed"]
    assert locks[0]["detail"] == "Sign-in refused: the account is locked"


def test_a_password_typed_as_the_username_is_not_logged():
    TestClient(app, headers=ORIGIN).post("/api/auth/login", json={"username": "my secret words 2026", "password": "x"})
    last = entries()[0]
    assert last["action"] == "sign_in_failed" and last["actor"] == "Unknown"
    assert "my secret words" not in str(entries())


def test_filters():
    security = entries(category="security")
    assert security and all(e["category"] == "security" for e in security)
    found = entries(q="campaign kit")
    assert found and all("campaign kit" in e["detail"] for e in found)
    body = admin.get("/api/admin/audit", params={"actor": "Audit Admin", "days": 1}).json()
    assert body["total"] >= 1 and all(e["actor"] == "Audit Admin" for e in body["entries"])
    assert "Audit Admin" in body["actors"]
    page = admin.get("/api/admin/audit", params={"limit": 2, "offset": 1}).json()["entries"]
    assert [e["seq"] for e in page] == [e["seq"] for e in entries()[1:3]]


def test_only_admins_see_the_audit_trail():
    for role in ("operator", "reviewer"):
        client = signed_in_client(role)
        assert client.get("/api/admin/audit").status_code == 403
        assert client.post("/api/admin/audit/verify").status_code == 403


# ---- the hash chain ----------------------------------------------------------------------------------


def test_each_row_points_to_the_row_before_it():
    audit.log("system", "test", "first")
    audit.log("system", "test", "second")
    with SessionLocal() as db:
        last, before = db.query(AuditEntry).order_by(AuditEntry.seq.desc()).limit(2).all()
        assert last.seq == before.seq + 1 and last.prev_hash == before.entry_hash
        assert len(last.entry_hash) == 64 and last.entry_hash != before.entry_hash
        first = db.get(AuditEntry, 1)
        assert first.prev_hash == audit.GENESIS


def test_the_database_refuses_to_change_or_delete_rows():
    with engine.begin() as connection:
        with pytest.raises(DatabaseError, match="append-only"):
            connection.execute(text("UPDATE audit_log SET detail = 'nothing happened' WHERE seq = 1"))
    with engine.begin() as connection:
        with pytest.raises(DatabaseError, match="append-only"):
            connection.execute(text("DELETE FROM audit_log WHERE seq = 1"))


def _unprotected(sql: str, **values) -> None:
    """What an attacker with the key could do: drop the rules, then change the table."""
    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER audit_log_no_update"))
        connection.execute(text("DROP TRIGGER audit_log_no_delete"))
        connection.execute(text(sql), values)
    protect_audit_log()


def test_verify_finds_the_first_changed_row():
    for n in range(3):
        audit.log("system", "test", f"row {n}")
    result = admin.post("/api/admin/audit/verify").json()
    assert result["ok"] and result["checked"] >= 3
    assert entries()[0]["detail"] == f"Audit chain checked · {result['checked']} of {result['checked']} rows intact"

    with SessionLocal() as db:
        target = db.query(AuditEntry).filter_by(action="sent_back").first() or db.get(AuditEntry, 2)
        seq, original = target.seq, target.detail

    try:
        # 1. change what a row says
        _unprotected("UPDATE audit_log SET detail = 'Approved at once' WHERE seq = :seq", seq=seq)
        broken = admin.post("/api/admin/audit/verify").json()
        assert broken["ok"] is False and broken["checked"] == seq - 1
        assert broken["broken"]["seq"] == seq and "content was changed" in broken["broken"]["reason"]
        assert broken["broken"]["entry"]["detail"] == "Approved at once"
        assert "BROKEN at row" in entries()[0]["detail"]

        # 2. ... and also work out its hash again: the NEXT row gives it away
        with SessionLocal() as db:
            row = db.get(AuditEntry, seq)
            new_hash = audit._content_hash(row)
        _unprotected("UPDATE audit_log SET entry_hash = :h WHERE seq = :seq", h=new_hash, seq=seq)
        broken = admin.post("/api/admin/audit/verify").json()
        assert broken["broken"]["seq"] == seq + 1 and "does not point to the row before" in broken["broken"]["reason"]
    finally:
        with SessionLocal() as db:
            row = db.get(AuditEntry, seq)
            row.detail = original
            fixed_hash = audit._content_hash(row)
            db.rollback()
        _unprotected("UPDATE audit_log SET detail = :d, entry_hash = :h WHERE seq = :seq",
                     d=original, h=fixed_hash, seq=seq)
    assert admin.post("/api/admin/audit/verify").json()["ok"]


def test_verify_finds_a_deleted_row():
    audit.log("system", "test", "to be deleted")
    audit.log("system", "test", "after it")
    with SessionLocal() as db:
        victim = db.query(AuditEntry).filter_by(detail="to be deleted").one()
        saved = {c.name: getattr(victim, c.name) for c in AuditEntry.__table__.columns}
    try:
        _unprotected("DELETE FROM audit_log WHERE seq = :seq", seq=saved["seq"])
        broken = admin.post("/api/admin/audit/verify").json()
        assert broken["broken"]["seq"] == saved["seq"] + 1
        assert broken["broken"]["reason"] == f"Row {saved['seq']} is missing (deleted?)"
    finally:
        with engine.begin() as connection:
            connection.execute(AuditEntry.__table__.insert(), saved)
    assert admin.post("/api/admin/audit/verify").json()["ok"]
