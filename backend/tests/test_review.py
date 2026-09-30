"""Stage 6B part 3: roles in the backend, the review flow (submit -> approve / send back), jobs frozen
while with a reviewer, separation of duties, the temporary-password gate, and the Admin's user routes.
(The full role x endpoint matrix is in test_permissions.py.)"""

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import ORIGIN, TEST_PASSWORD, signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "review.operator")
reviewer = signed_in_client("reviewer", "review.reviewer")
admin = signed_in_client("admin", "review.admin")


def finished_job(client: TestClient = operator) -> dict:
    """A job with two finished outputs (the mock AI is instant)."""
    response = client.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                              "outputs": ["x_thread", "executive_summary"]})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready", done["error"]
    return done


def test_the_job_remembers_who_made_it():
    job = finished_job()
    assert job["owner"]["full_name"] == "Review Operator"
    assert job["reviews"] == []
    assert job["safety_decisions"][-1]["actor"] == "Review Operator"


def test_submit_send_back_resubmit_and_approve():
    job = finished_job()
    url = f"/api/jobs/{job['id']}"
    x_thread = next(o for o in job["outputs"] if o["type"] == "x_thread")
    edit = {"fields": [{"path": ["tweets", 0, "text"], "text": "Patch your VPN today."}]}

    # a reviewer cannot review what has not been submitted, nor change anything
    assert reviewer.post(f"{url}/review", json={"decision": "approve"}).status_code == 409
    assert reviewer.put(f"{url}/outputs/{x_thread['id']}", json=edit).status_code == 403

    submitted = operator.post(f"{url}/submit", json={"notes": "Ready for the morning briefing"})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"
    assert operator.post(f"{url}/submit", json={}).status_code == 409  # already there

    # frozen while with the reviewer
    frozen = operator.put(f"{url}/outputs/{x_thread['id']}", json=edit)
    assert frozen.status_code == 409 and "with a reviewer" in frozen.json()["detail"]
    assert operator.post(f"{url}/outputs/{x_thread['id']}/regenerate").status_code == 409
    assert operator.post(f"{url}/retry").status_code == 409

    queue = reviewer.get("/api/review/queue").json()
    item = next(i for i in queue["waiting"] if i["id"] == job["id"])
    assert item["can_review"] and item["owner"] == "Review Operator"
    assert item["submit_notes"] == "Ready for the morning briefing" and item["version"] == 1

    # sending back needs a note for the operator
    assert reviewer.post(f"{url}/review", json={"decision": "send_back"}).status_code == 400
    back = reviewer.post(f"{url}/review", json={"decision": "send_back", "notes": "Add the helpline number."})
    assert back.status_code == 200 and back.json()["status"] == "sent_back"
    assert not any(i["id"] == job["id"] for i in reviewer.get("/api/review/queue").json()["waiting"])

    # the operator sees the notes, changes the job and sends it again as version 2
    seen = operator.get(url).json()
    assert seen["reviews"][-1] | {"created_at": None} == {
        "decision": "sent_back", "by": "Review Reviewer", "user_id": seen["reviews"][-1]["user_id"],
        "notes": "Add the helpline number.", "version": 1, "created_at": None}
    assert operator.put(f"{url}/outputs/{x_thread['id']}", json=edit).status_code == 200
    again = operator.post(f"{url}/submit", json={}).json()
    assert again["status"] == "in_review" and again["version"] == 2

    approved = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert [r["decision"] for r in approved.json()["reviews"]] == ["submitted", "sent_back", "submitted", "approved"]
    assert operator.put(f"{url}/outputs/{x_thread['id']}", json=edit).status_code == 409
    assert "approved" in operator.post(f"{url}/submit", json={}).json()["detail"]
    recent = reviewer.get("/api/review/queue").json()["recent"]
    assert recent[0]["job_id"] == job["id"] and recent[0]["decision"] == "approved"


def test_a_reviewer_cannot_approve_their_own_job():
    """Separation of duties: Farhan made a job as an Operator, then became a Reviewer."""
    farhan = signed_in_client("operator", "farhan.ali")
    job = finished_job(farhan)
    assert farhan.post(f"/api/jobs/{job['id']}/submit", json={}).status_code == 200

    users = admin.get("/api/admin/users").json()
    farhan_id = next(u["id"] for u in users if u["username"] == "farhan.ali")
    assert admin.put(f"/api/admin/users/{farhan_id}", json={"role": "reviewer"}).status_code == 200

    item = next(i for i in farhan.get("/api/review/queue").json()["waiting"] if i["id"] == job["id"])
    assert item["can_review"] is False and "separation of duties" in item["why_not"]
    for decision in ({"decision": "approve"}, {"decision": "send_back", "notes": "Looks fine to me"}):
        refused = farhan.post(f"/api/jobs/{job['id']}/review", json=decision)
        assert refused.status_code == 403 and "separation of duties" in refused.json()["detail"]
    # another reviewer can
    assert reviewer.post(f"/api/jobs/{job['id']}/review", json={"decision": "approve"}).status_code == 200


def test_admins_do_not_see_content_and_others_cannot_manage_users():
    job = finished_job()
    assert admin.get(f"/api/jobs/{job['id']}").status_code == 403
    assert admin.post(f"/api/jobs/{job['id']}/review", json={"decision": "approve"}).status_code == 403
    for client in (operator, reviewer):
        refused = client.get("/api/admin/users")
        assert refused.status_code == 403 and "Only Admins" in refused.json()["detail"]
    assert TestClient(app, headers=ORIGIN).get("/api/jobs").status_code == 401


def test_admin_adds_a_user_who_must_choose_a_password_first():
    made = admin.post("/api/admin/users", json={"username": "Meera.Iyer", "full_name": "Meera Iyer",
                                                "role": "reviewer"})
    assert made.status_code == 201, made.text
    temporary = made.json()["temporary_password"]
    assert made.json()["user"]["must_change_password"] and "password_hash" not in made.json()["user"]

    meera = TestClient(app, headers=ORIGIN)
    signed = meera.post("/api/auth/login", json={"username": "meera.iyer", "password": temporary})
    assert signed.status_code == 200 and signed.json()["user"]["must_change_password"]
    gated = meera.get("/api/review/queue")
    assert gated.status_code == 403 and "new password" in gated.json()["detail"]
    assert meera.get("/api/auth/me").status_code == 200  # allowed: to show the Change password screen
    changed = meera.post("/api/auth/change-password", json={"current_password": temporary,
                                                            "new_password": "a long passphrase of her own"})
    assert changed.status_code == 200 and not changed.json()["user"]["must_change_password"]
    assert meera.get("/api/review/queue").status_code == 200


def test_admin_reset_password_signs_the_user_out_and_unlocks():
    lakshmi = signed_in_client("operator", "lakshmi.rao")
    lakshmi_id = next(u["id"] for u in admin.get("/api/admin/users").json() if u["username"] == "lakshmi.rao")
    reset = admin.post(f"/api/admin/users/{lakshmi_id}/reset-password")
    assert reset.status_code == 200 and reset.json()["user"]["must_change_password"]
    assert lakshmi.get("/api/jobs").status_code == 401  # signed out everywhere
    assert admin.post(f"/api/admin/users/{lakshmi_id}/reset-password").json()["temporary_password"] != \
        reset.json()["temporary_password"]


def test_admin_switches_a_user_off_and_back_on():
    rohit = signed_in_client("operator", "rohit.verma")
    rohit_id = next(u["id"] for u in admin.get("/api/admin/users").json() if u["username"] == "rohit.verma")
    off = admin.put(f"/api/admin/users/{rohit_id}", json={"is_active": False})
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert rohit.get("/api/jobs").status_code == 401
    login = TestClient(app, headers=ORIGIN).post("/api/auth/login", json={"username": "rohit.verma",
                                                                         "password": TEST_PASSWORD})
    assert login.status_code == 401 and "switched off" in login.json()["detail"]
    assert admin.put(f"/api/admin/users/{rohit_id}", json={"is_active": True}).json()["is_active"] is True


def test_admin_approves_and_rejects_access_requests():
    anonymous = TestClient(app, headers=ORIGIN)
    for username, name in (("sneha.patil", "Sneha Patil"), ("spam.user", "Spam User")):
        response = anonymous.post("/api/auth/request-access", json={
            "username": username, "full_name": name, "role": "operator", "reason": "Research and analysis",
            "password": TEST_PASSWORD})
        assert response.status_code == 201, response.text
    requests = {r["username"]: r for r in admin.get("/api/admin/requests").json() if r["status"] == "pending"}
    assert "password_hash" not in requests["sneha.patil"]

    approved = admin.post(f"/api/admin/requests/{requests['sneha.patil']['id']}/approve", json={"role": "reviewer"})
    assert approved.status_code == 200 and approved.json()["user"]["role"] == "reviewer"
    assert admin.post(f"/api/admin/requests/{requests['spam.user']['id']}/reject").status_code == 200
    assert admin.post(f"/api/admin/requests/{requests['spam.user']['id']}/approve", json={}).status_code == 409

    sneha = TestClient(app, headers=ORIGIN)
    assert sneha.post("/api/auth/login", json={"username": "sneha.patil", "password": TEST_PASSWORD}).status_code == 200
    assert sneha.get("/api/review/queue").status_code == 200
    assert anonymous.post("/api/auth/login", json={"username": "spam.user", "password": TEST_PASSWORD}).status_code == 401
