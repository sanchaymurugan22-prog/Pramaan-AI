"""Stage 9B part 5a: Admin overview, AI models and performance (from real runs) with a speed test, and the
security policy (scanner switches, extra classification words, inactivity sign-out, lockout) really applied."""

import uuid
from contextlib import contextmanager
from datetime import timedelta

from fastapi.testclient import TestClient

from app import app_settings
from app.db import SessionLocal, UserSession, utc_now
from app.main import app
from app.safety.scanner import ScanSource, scan_sources
from tests.auth_helpers import ORIGIN, TEST_PASSWORD, make_user, signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

admin = signed_in_client("admin", "system.admin")
operator = signed_in_client("operator", "system.operator")


@contextmanager
def policy(**change):
    """Change the security policy for one test, then put the default back."""
    response = admin.put("/api/admin/security", json=change)
    assert response.status_code == 200, response.text
    try:
        yield response.json()
    finally:
        app_settings.put("security", app_settings.DEFAULTS["security"])


def kinds(text: str) -> list[str]:
    return [f["kind"] for f in scan_sources([ScanSource("S1", "t", [text], [])])["findings"]]


def test_overview_counts_and_checker_counter():
    before = admin.get("/api/admin/overview").json()
    assert before["users"]["admin"] >= 1 and before["computer"]["processors"] >= 1
    assert before["computer"]["encrypted"] is True
    operator.post("/api/check-message", json={"text": "Your electricity will be cut tonight. Pay now at http://bit.ly/x"})
    after = admin.get("/api/admin/overview").json()
    assert after["checker"]["checks"] == before["checker"]["checks"] + 1
    # requests waiting appear
    TestClient(app, headers=ORIGIN).post("/api/auth/request-access", json={
        "full_name": "Waiting Person", "employee_id": f"W-{uuid.uuid4().hex[:6]}", "role": "operator", "password": TEST_PASSWORD})
    assert any(r["full_name"] == "Waiting Person" for r in admin.get("/api/admin/overview").json()["requests"])


def test_ai_page_measures_real_runs_and_speed_test():
    job = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8") + uuid.uuid4().hex,
                                           "outputs": ["x_thread"]}).json()
    wait_for(job["id"])
    body = admin.get("/api/admin/ai").json()
    assert body["ai_mode"] == "mock" and any(m["status"] == "in_use" for m in body["models"])
    mock = next(p for p in body["performance"] if p["ai_mode"] == "mock")
    assert mock["outputs"] >= 1 and mock["by_type"]
    test = admin.post("/api/admin/ai/speed-test").json()
    assert test["ai_mode"] == "mock" and test["ok"] and test["seconds"] >= 0
    assert admin.get("/api/admin/ai").json()["speed_test"]["at"] == test["at"]


def test_scanner_switches_and_extra_words_apply():
    text = "Call 98765 43210. This note is INTERNAL ONLY."
    assert "phone" in kinds(text) and "classification" not in kinds(text)
    with policy(scanner={"phone": False}, classification_words=["internal only"]) as state:
        assert next(s for s in state["scanner"] if s["key"] == "phone")["on"] is False
        found = kinds(text)
        assert "phone" not in found and "classification" in found
        log = admin.get("/api/admin/audit?q=security policy").json()["entries"][0]
        assert "Phone numbers OFF" in log["detail"]
    assert "phone" in kinds(text)  # back to the default
    assert admin.put("/api/admin/security", json={"scanner": {"nope": True}}).status_code == 400
    assert admin.put("/api/admin/security", json={"classification_words": ["<script>"]}).status_code == 400


def test_inactivity_and_lockout_policy_apply():
    client = signed_in_client("operator", "system.idle")
    with SessionLocal() as db:  # pretend the last request was 20 minutes ago
        for row in db.query(UserSession).all():
            if row.user.username == "system.idle":
                row.last_seen = utc_now() - timedelta(minutes=20)
        db.commit()
    with policy(idle_minutes=15):
        ended = client.get("/api/auth/me")
        assert ended.status_code == 401 and "15 minutes" in ended.json()["detail"]

    make_user("system.locky", "operator")
    anyone = TestClient(app, headers=ORIGIN)
    with policy(lock_after=3):
        for _ in range(2):
            assert anyone.post("/api/auth/login", json={"username": "system.locky", "password": "wrong password!"}).status_code == 401
        locked = anyone.post("/api/auth/login", json={"username": "system.locky", "password": "wrong password!"})
        assert locked.status_code == 423 and "3 wrong passwords" in locked.json()["detail"]
    assert admin.put("/api/admin/security", json={"idle_minutes": 7}).status_code == 400
