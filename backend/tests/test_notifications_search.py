"""Stage 9A part 1: in-app notifications (finished, submitted, sent back, approved, signed), the job list's
new fields and filters, the search box across jobs / sources / records, and the dashboard numbers."""

from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "notes.operator")
reviewer = signed_in_client("reviewer", "notes.reviewer")
other_operator = signed_in_client("operator", "notes.other")
admin = signed_in_client("admin", "notes.admin")


def finished_job(title: str) -> dict:
    response = operator.post("/api/jobs", data={"title": title, "text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": ["x_thread"]})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready", done["error"]
    return done


def notes_for(client, job_id: int) -> list[dict]:
    return [n for n in client.get("/api/notifications").json()["items"] if n["job_id"] == job_id]


def test_finished_sent_back_approved_and_signed_notifications():
    job = finished_job("Notifications test job")
    finished = notes_for(operator, job["id"])
    assert [n["kind"] for n in finished] == ["finished"]
    assert finished[0]["title"] == "All 1 output is ready" and not finished[0]["read"]
    assert notes_for(other_operator, job["id"]) == []  # only the job's own Operator

    url = f"/api/jobs/{job['id']}"
    assert operator.post(f"{url}/submit", json={}).status_code == 200
    assert [n["kind"] for n in notes_for(reviewer, job["id"])] == ["submitted"]
    assert notes_for(operator, job["id"])[0]["kind"] == "finished"  # the submitter is not told about their own action

    sent_back = reviewer.post(f"{url}/review", json={"decision": "send_back", "notes": "Check the dates please"})
    assert sent_back.status_code == 200, sent_back.text
    newest = notes_for(operator, job["id"])[0]
    assert newest["kind"] == "sent_back" and "Check the dates please" in newest["detail"]

    assert operator.post(f"{url}/submit", json={}).status_code == 200
    approved = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    kinds = [n["kind"] for n in notes_for(operator, job["id"])]
    assert kinds[:2] == ["signed", "approved"]
    signed = notes_for(operator, job["id"])[0]
    assert approved.json()["record"]["record_no"] in signed["title"]


def test_read_one_and_read_all_only_touch_my_own():
    job = finished_job("Read notifications")
    mine = notes_for(operator, job["id"])[0]
    # someone else cannot mark it read (and cannot tell that it exists)
    assert other_operator.post(f"/api/notifications/{mine['id']}/read").status_code == 404
    before = operator.get("/api/notifications/count").json()["unread"]
    assert before >= 1
    after = operator.post(f"/api/notifications/{mine['id']}/read").json()["unread"]
    assert after == before - 1
    assert notes_for(operator, job["id"])[0]["read"]
    unread_only = operator.get("/api/notifications?unread=true").json()["items"]
    assert all(not n["read"] for n in unread_only)
    assert operator.post("/api/notifications/read-all").json() == {"unread": 0}
    assert operator.get("/api/notifications/count").json() == {"unread": 0}


def test_job_list_has_the_new_fields_and_filters():
    job = finished_job("Filter test: quarterly phishing summary")
    row = next(j for j in operator.get("/api/jobs").json() if j["id"] == job["id"])
    assert row["ai_mode"] == "mock" and row["tlp"] == "GREEN" and row["version"] == 1
    assert row["quality_score"] is not None and row["created_via"] == "manual" and row["languages"] == ["en"]

    def ids(query: str) -> list[int]:
        return [j["id"] for j in operator.get(f"/api/jobs?{query}").json()]

    assert job["id"] in ids("q=quarterly phishing")
    assert job["id"] in ids(f"q=%23{job['id']:04d}")  # "#0012": the job number as shown on the page
    assert job["id"] not in ids("q=no such title anywhere")
    assert job["id"] in ids("status=ready,draft") and job["id"] not in ids("status=approved")
    assert job["id"] in ids("tlp=green") and job["id"] not in ids("tlp=RED")
    assert job["id"] in ids("days=30")


def test_search_finds_jobs_sources_and_records_by_role():
    job = finished_job("Searchable monsoon advisory")
    found = operator.get("/api/search?q=monsoon").json()
    assert job["id"] in [j["id"] for j in found["jobs"]]
    # pasted text is stored as a source called "Pasted text"
    by_file = operator.get(f"/api/search?q={job['sources'][0]['filename'][:6]}").json()
    assert any(s["job_id"] == job["id"] for s in by_file["sources"])
    by_hash = operator.get(f"/api/search?q={job['sources'][0]['sha256'][:12]}").json()
    assert any(s["job_id"] == job["id"] for s in by_hash["sources"])
    assert operator.get("/api/search?q=m").json() == {"jobs": [], "sources": [], "records": []}  # too short

    url = f"/api/jobs/{job['id']}"
    operator.post(f"{url}/submit", json={})
    record_no = reviewer.post(f"{url}/review", json={"decision": "approve"}).json()["record"]["record_no"]
    by_record = reviewer.get(f"/api/search?q={record_no}").json()
    assert [r["record_no"] for r in by_record["records"]] == [record_no]
    # Admins do not see job content: records only
    admin_found = admin.get("/api/search?q=monsoon").json()
    assert admin_found["jobs"] == [] and admin_found["sources"] == []
    assert record_no in [r["record_no"] for r in admin_found["records"]]


def test_dashboard_numbers_and_attention():
    job = finished_job("Dashboard attention job")
    body = operator.get("/api/dashboard").json()
    assert body["stats"]["jobs_this_week"] >= 1
    assert body["encrypted"] is True
    assert any(item["job_id"] == job["id"] for item in body["attention"])
    url = f"/api/jobs/{job['id']}"
    operator.post(f"{url}/submit", json={})
    reviewer.post(f"{url}/review", json={"decision": "send_back", "notes": "Fix the district names"})
    first = operator.get("/api/dashboard").json()["attention"][0]
    assert first["kind"] == "sent_back" and "Fix the district names" in first["detail"]
