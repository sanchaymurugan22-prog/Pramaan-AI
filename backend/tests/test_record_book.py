"""Stage 7 part 2: the record book. Withdrawing (a new signed entry, never a change), and "Verify record
book" finding the first changed, re-written or deleted entry, or a changed signed file."""

import json
import os

from sqlalchemy import text

from app import crypto
from app.db import Record, SessionLocal, engine, protect_append_only
from app.signing import records
from app.signing.sign_job import signed_dir
from app.signing.signer import get_signer
from tests.auth_helpers import signed_in_client
from tests.test_signing import approved_job

admin = signed_in_client("admin", "book.admin")
reviewer = signed_in_client("reviewer", "book.reviewer")
operator = signed_in_client("operator", "book.operator")


def verify() -> dict:
    response = admin.post("/api/records/verify")
    assert response.status_code == 200
    return response.json()


def test_withdraw_adds_a_signed_entry_and_never_changes_the_record():
    job = approved_job(outputs=("x_thread",))
    record_no = job["record"]["record_no"]
    with SessionLocal() as db:
        before = records.find_issue(db, record_no).entry_hash

    assert admin.post(f"/api/admin/records/{record_no}/withdraw", json={"reason": "no"}).status_code == 400
    response = admin.post(f"/api/admin/records/{record_no}/withdraw", json={"reason": "Replaced by a corrected advisory"})
    assert response.status_code == 200, response.text
    assert response.json()["withdrawn"]["reason"] == "Replaced by a corrected advisory"
    again = admin.post(f"/api/admin/records/{record_no}/withdraw", json={"reason": "Twice is not allowed"})
    assert again.status_code == 400 and "already withdrawn" in again.json()["detail"]
    assert admin.post("/api/admin/records/PRM-1999-000001/withdraw", json={"reason": "Not there at all"}).status_code == 404

    with SessionLocal() as db:
        issue, withdrawal = records.find_issue(db, record_no), records.withdrawal_of(db, record_no)
        assert issue.entry_hash == before  # unchanged
        assert withdrawal.seq > issue.seq and withdrawal.kind == "withdraw"
        assert withdrawal.prev_hash == db.get(Record, withdrawal.seq - 1).entry_hash  # chained like any entry
        public = json.loads(withdrawal.public_manifest)
        assert public["kind"] == "withdraw" and public["reason"] == "Replaced by a corrected advisory"

    # everyone who opens the job sees it
    assert operator.get(f"/api/jobs/{job['id']}").json()["record"]["withdrawn"]["reason"]
    listed = next(r for r in reviewer.get("/api/records").json()["records"] if r["record_no"] == record_no)
    assert listed["status"] == "withdrawn"
    assert verify()["ok"]


def test_a_restricted_record_publishes_only_a_general_withdrawal_reason():
    job = approved_job(outputs=("advisory",), tlp="RED")
    record_no = job["record"]["record_no"]
    admin.post(f"/api/admin/records/{record_no}/withdraw", json={"reason": "Operation Kestrel details were wrong"})
    with SessionLocal() as db:
        public = json.loads(records.withdrawal_of(db, record_no).public_manifest)
    assert public["reason"] == "Withdrawn by the issuing office." and "Kestrel" not in json.dumps(public)


def test_the_list_search_and_replaced_status():
    job = approved_job(outputs=("x_thread",))
    first = job["record"]["record_no"]
    operator.post(f"/api/jobs/{job['id']}/new-version")
    operator.post(f"/api/jobs/{job['id']}/submit", json={})
    second = reviewer.post(f"/api/jobs/{job['id']}/review", json={"decision": "approve"}).json()["record"]["record_no"]
    body = reviewer.get("/api/records", params={"q": first}).json()
    [item] = body["records"]
    assert item["status"] == "replaced" and item["replaced_by"] == second and item["files_count"] == 1
    assert body["counts"]["replaced"] >= 1 and body["entries"] >= 2
    assert [c["seq"] for c in body["chain"]] == sorted(c["seq"] for c in body["chain"])
    assert all(b["prev_hash"] == a["entry_hash"] for a, b in zip(body["chain"], body["chain"][1:]))


def test_verify_record_book_is_intact_and_logged():
    approved_job(outputs=("x_thread",))
    result = verify()
    assert result["ok"] and result["checked"] >= 1 and result["files_checked"] >= 1
    assert reviewer.get("/api/records").json()["last_check"]["detail"].startswith("Record book checked")


def test_the_database_refuses_to_change_or_delete_records():
    approved_job(outputs=("x_thread",))
    for sql in ("UPDATE records SET manifest = 'x' WHERE seq = 1", "DELETE FROM records WHERE seq = 1"):
        with engine.begin() as connection:
            try:
                connection.execute(text(sql))
                raise AssertionError("the database allowed it")
            except Exception as exc:  # noqa: BLE001 (sqlcipher raises its own IntegrityError class)
                assert "append-only" in str(exc)


def _unprotected(sql: str, **values) -> None:
    """What an attacker with the database key could do: drop the rules, then change the table."""
    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER records_no_update"))
        connection.execute(text("DROP TRIGGER records_no_delete"))
        connection.execute(text(sql), values)
    protect_append_only("records", "The record book is append-only")


def test_verify_finds_a_changed_entry_even_if_its_hash_is_redone():
    job = approved_job(outputs=("x_thread",))
    approved_job(outputs=("x_thread",))  # an entry after it
    with SessionLocal() as db:
        entry = records.find_issue(db, job["record"]["record_no"])
        seq, original_manifest, original_hash = entry.seq, entry.manifest, entry.entry_hash
    forged = original_manifest.replace('"Sign Reviewer"', '"Someone Else"')  # approved_job's reviewer
    assert forged != original_manifest
    try:
        # 1. change what it says
        _unprotected("UPDATE records SET manifest = :m WHERE seq = :s", m=forged, s=seq)
        broken = verify()
        assert not broken["ok"] and broken["broken"]["seq"] == seq
        assert "content was changed" in broken["broken"]["reason"] and broken["checked"] == seq - 1

        # 2. also work its hash out again: the signature (and the next entry) give it away
        with SessionLocal() as db:
            new_hash = records.entry_hash(db.get(Record, seq))
        _unprotected("UPDATE records SET entry_hash = :h WHERE seq = :s", h=new_hash, s=seq)
        broken = verify()
        assert broken["broken"]["seq"] == seq and "signature does not match" in broken["broken"]["reason"]
    finally:
        _unprotected("UPDATE records SET manifest = :m, entry_hash = :h WHERE seq = :s",
                     m=original_manifest, h=original_hash, s=seq)
    assert verify()["ok"]


def test_verify_finds_a_deleted_entry():
    approved_job(outputs=("x_thread",))
    approved_job(outputs=("x_thread",))
    with SessionLocal() as db:
        victim = db.get(Record, records.last_entry(db).seq - 1)
        saved = {c.name: getattr(victim, c.name) for c in Record.__table__.columns}
    try:
        _unprotected("DELETE FROM records WHERE seq = :s", s=saved["seq"])
        broken = verify()
        assert broken["broken"]["seq"] == saved["seq"] + 1
        assert broken["broken"]["reason"] == f"Entry {saved['seq']} is missing (deleted?)"
    finally:
        with engine.begin() as connection:
            connection.execute(Record.__table__.insert(), saved)
    assert verify()["ok"]


def test_verify_finds_a_changed_signed_file():
    job = approved_job(outputs=("x_thread",))
    path = next(signed_dir(job["id"], job["record"]["record_no"]).iterdir())
    original = crypto.read_file(path)
    os.chmod(path, 0o644)
    try:
        crypto.write_file(path, original.replace(b"Approved", b"Accepted"))  # a re-encrypted, edited copy
        broken = verify()
        assert broken["broken"]["record_no"] == job["record"]["record_no"]
        assert "fingerprint differs" in broken["broken"]["reason"]
    finally:
        crypto.write_file(path, original)
        os.chmod(path, 0o444)
    assert verify()["ok"]


def test_a_record_signed_with_another_key_is_reported(tmp_path):
    from app.signing.signer import TestSigner
    approved_job(outputs=("x_thread",))
    other = TestSigner(tmp_path)  # a different key, as if someone swapped the published public key
    with SessionLocal() as db:
        result = records.verify_book(db, other.public_key_pem(), check_files=False)
        assert not result["ok"] and result["broken"]["seq"] == 1 and "different key" in result["broken"]["reason"]
        assert records.verify_book(db, get_signer().public_key_pem(), check_files=False)["ok"]
