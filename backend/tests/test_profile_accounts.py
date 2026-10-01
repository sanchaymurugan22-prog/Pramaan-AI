"""Stage 9B part 1: employee ID, email, division and language on accounts and access requests; signing in
with any of username / employee ID / email; Profile & settings (own language and preferences only);
notification preferences; the public options and "this computer" check."""

import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal, User
from app.main import app
from tests.auth_helpers import ORIGIN, TEST_PASSWORD, make_user, signed_in_client

anyone = TestClient(app, headers=ORIGIN)
admin = signed_in_client("admin", "profile.admin")


def unique() -> str:
    return uuid.uuid4().hex[:6].upper()


def test_public_options_and_computer_check():
    body = anyone.get("/api/auth/options").json()
    assert len(body["languages"]) == 23 and body["languages"][0] == {"code": "en", "name": "English"}
    assert "Cyber operations" in body["divisions"]
    # only before First-time setup (there are users in the test database)
    assert anyone.get("/api/auth/computer").status_code == 409


def test_request_access_with_employee_id_and_sign_in_with_it():
    emp = f"EMP-{unique()}"
    form = {"full_name": "Rahul Kumar", "employee_id": emp.lower(), "email": f"rahul.{emp.lower()}@org.gov.in",
            "division": "Cyber operations", "language": "hi", "role": "operator", "password": TEST_PASSWORD}
    sent = anyone.post("/api/auth/request-access", json=form)
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["username"] == emp.lower() and body["employee_id"] == emp and "Profile Admin" in body["admins"]
    # the same employee ID cannot ask twice; signing in says it is still waiting
    assert anyone.post("/api/auth/request-access", json=form | {"email": ""}).status_code == 400
    waiting = anyone.post("/api/auth/login", json={"username": emp, "password": TEST_PASSWORD})
    assert waiting.status_code == 401 and "waiting" in waiting.json()["detail"]

    request = next(r for r in admin.get("/api/admin/requests").json() if r["employee_id"] == emp)
    assert request["division"] == "Cyber operations" and request["email"] == form["email"]
    user = admin.post(f"/api/admin/requests/{request['id']}/approve", json={}).json()["user"]
    assert user["employee_id"] == emp and user["email"] == form["email"]

    client = TestClient(app, headers=ORIGIN)
    for typed in (emp.lower(), form["email"].upper(), emp.lower()):  # employee ID, email (any case), username
        signed = client.post("/api/auth/login", json={"username": typed, "password": TEST_PASSWORD})
        assert signed.status_code == 200, (typed, signed.text)
        me = signed.json()["user"]
        assert me["language"] == "hi" and me["division"] == "Cyber operations"


def test_bad_details_are_refused():
    base = {"full_name": "Asha Rao", "role": "operator", "password": TEST_PASSWORD}
    assert anyone.post("/api/auth/request-access", json=base).status_code == 400  # no employee ID or username
    assert anyone.post("/api/auth/request-access", json=base | {"employee_id": "EMP 1!"}).status_code == 400
    assert anyone.post("/api/auth/request-access", json=base | {"employee_id": f"E-{unique()}", "email": "not-an-email"}).status_code == 400
    assert anyone.post("/api/auth/request-access", json=base | {"employee_id": f"E-{unique()}", "language": "xx"}).status_code == 400


def test_admin_adds_and_edits_users_with_the_new_details():
    emp = f"EMP-{unique()}"
    made = admin.post("/api/admin/users", json={"full_name": "Meera Iyer", "role": "reviewer", "employee_id": emp,
                                                "email": f"meera.{emp.lower()}@org.gov.in", "division": "Public communication",
                                                "dsc_holder": True, "emergency_duty": True})
    assert made.status_code == 201, made.text
    user = made.json()["user"]
    assert user["username"] == emp.lower() and user["dsc_holder"] and user["emergency_duty"]
    # another account cannot take the same employee ID
    clash = admin.post("/api/admin/users", json={"full_name": "Someone Else", "role": "operator", "employee_id": emp})
    assert clash.status_code == 400 and "employee ID" in clash.json()["detail"]
    changed = admin.put(f"/api/admin/users/{user['id']}", json={"division": "Cyber operations", "dsc_holder": False,
                                                               "email": ""})
    assert changed.status_code == 200
    assert changed.json()["division"] == "Cyber operations" and changed.json()["email"] is None
    assert not changed.json()["dsc_holder"]


def test_profile_changes_only_language_and_preferences():
    client = signed_in_client("operator", "profile.operator")
    body = client.get("/api/profile").json()
    assert body["user"]["username"] == "profile.operator" and len(body["languages"]) == 23
    saved = client.put("/api/profile", json={"language": "ta", "prefs": {"text_size": "large", "high_contrast": True,
                                                                       "output_languages": ["en", "ta"]}})
    assert saved.status_code == 200, saved.text
    me = saved.json()["user"]
    assert me["language"] == "ta" and me["prefs"]["text_size"] == "large" and me["prefs"]["output_languages"] == ["en", "ta"]
    assert client.put("/api/profile", json={"prefs": {"text_size": "huge"}}).status_code == 400
    assert client.put("/api/profile", json={"prefs": {"role": "admin"}}).status_code == 400
    # identity fields are not part of the form: they are ignored, the role stays
    client.put("/api/profile", json={"role": "admin", "employee_id": "EMP-HACK"})
    assert client.get("/api/auth/me").json()["user"]["role"] == "operator"


def test_notification_preferences_switch_off_ready_notes():
    client = signed_in_client("operator", "profile.quiet")
    client.put("/api/profile", json={"prefs": {"notify_ready": False}})
    from tests.helpers import SAMPLE_REPORT
    from tests.test_jobs_api import wait_for
    job = client.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8") + unique(),
                                         "outputs": ["x_thread"]}).json()
    wait_for(job["id"])
    assert all(n["job_id"] != job["id"] for n in client.get("/api/notifications").json()["items"])


def test_emergency_alerts_go_to_the_reviewers_on_duty():
    on_duty = make_user("profile.onduty", "reviewer", emergency_duty=True)
    off_duty = make_user("profile.offduty", "reviewer", emergency_duty=False)
    operator = signed_in_client("operator", "profile.alerter")
    sent = operator.post("/api/alerts", json={"type": "Flood", "severity": "Warning",
                                              "message": f"Flood warning {unique()}: move to higher ground if water rises. Call 112."})
    assert sent.status_code == 201, sent.text
    from tests.test_jobs_api import wait_for
    wait_for(sent.json()["id"])
    with SessionLocal() as db:
        from app.db import Notification
        told = {n.user_id for n in db.query(Notification).filter_by(job_id=sent.json()["id"], kind="alert")}
        assert on_duty.id in told and off_duty.id not in told
        db.query(User).filter_by(id=on_duty.id).update({"emergency_duty": False})
        db.commit()
