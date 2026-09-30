"""End-to-end tests of the job API with the mock AI: create a job, wait for it, read the results."""

import time

from tests.helpers import SAMPLE_REPORT, make_pdf
from fastapi.testclient import TestClient

from app.ai import llm
from app.main import app
from app.pipeline import generate, runner

client = TestClient(app)


def wait_for(job_id: int, timeout: float = 10.0) -> dict:
    """Poll the job until it stops generating (the mock AI is instant, so this is quick)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "generating":
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} still generating after {timeout}s")


def test_options_lists_the_seven_outputs():
    body = client.get("/api/options").json()
    assert [o["key"] for o in body["output_types"]] == [
        "x_thread", "linkedin_post", "executive_summary", "infographic", "advisory", "presentation", "video_package",
    ]
    assert body["default_settings"]["detail_level"] == "medium"


def test_pasted_text_with_two_outputs():
    response = client.post("/api/jobs", data={
        "text": SAMPLE_REPORT.read_text(encoding="utf-8"),
        "outputs": ["linkedin_post", "x_thread"],
        "audience": "General public",
    })
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "generating"
    assert created["title"] == "Incident report: ransomware campaign affecting hospital networks"

    job = wait_for(created["id"])
    assert job["status"] == "ready", job["error"]
    assert job["settings"]["audience"] == "General public"
    assert job["fact_sheet"]["key_facts"][0]["quote_found"] == "exact"
    # short outputs first, whatever order they were ticked in
    assert [o["type"] for o in job["outputs"]] == ["x_thread", "linkedin_post"]
    assert all(o["status"] == "done" for o in job["outputs"])

    x_thread, linkedin = job["outputs"]
    assert x_thread["quality"]["unlinked"] == []
    # the mock LinkedIn post has one paragraph with no fact ids: it must be flagged, not dropped
    assert linkedin["quality"]["unlinked"] == ["Cyber hygiene is a leadership responsibility, not just an IT task."]
    assert linkedin["quality"]["warnings"]


def test_file_upload_with_all_outputs():
    files = [
        ("files", (SAMPLE_REPORT.name, SAMPLE_REPORT.read_bytes(), "text/plain")),
        ("files", ("extra.pdf", make_pdf(["Extra page one", "Extra page two"]), "application/pdf")),
    ]
    all_outputs = [o["key"] for o in client.get("/api/options").json()["output_types"]]
    response = client.post("/api/jobs", data={"outputs": all_outputs, "title": "Hospital ransomware"}, files=files)
    assert response.status_code == 201, response.text

    job = wait_for(response.json()["id"])
    assert job["status"] == "ready", job["error"]
    assert job["title"] == "Hospital ransomware"
    assert [(s["id"], s["kind"], s["pages"]) for s in job["sources"]] == [("S1", "txt", 1), ("S2", "pdf", 2)]
    outputs = {o["type"]: o for o in job["outputs"]}
    assert all(o["status"] == "done" for o in outputs.values())

    advisory = outputs["advisory"]["content"]
    assert advisory["indicators"]["ips"] == ["203.0.113.45", "198.51.100.23"]  # added from the source by code

    video = outputs["video_package"]["content"]
    assert video["subtitles"][0]["start"] == "00:00:00,000"
    assert video["duration_seconds"] > 0
    assert video["scenes"][1]["start"] == video["scenes"][0]["end"]


def test_job_list_and_missing_job():
    jobs = client.get("/api/jobs").json()
    assert jobs and {"id", "title", "status", "outputs_done", "outputs_total"} <= set(jobs[0])
    assert client.get("/api/jobs/999999").status_code == 404


def test_bad_requests_get_clear_messages():
    no_source = client.post("/api/jobs", data={"outputs": ["x_thread"]})
    assert no_source.status_code == 400
    assert "Paste some text" in no_source.json()["detail"]

    bad_output = client.post("/api/jobs", data={"text": "hello there", "outputs": ["poem"]})
    assert bad_output.status_code == 400
    assert "poem" in bad_output.json()["detail"]

    bad_file = client.post("/api/jobs", data={"outputs": ["x_thread"]}, files={"files": ("a.png", b"x", "image/png")})
    assert bad_file.status_code == 400


def test_failed_output_can_be_retried(monkeypatch):
    real_generate = generate.generate_output

    def flaky(output_type, fact_sheet, job_settings, **kwargs):
        if output_type == "linkedin_post":
            raise llm.LLMError("The AI server took too long.")
        return real_generate(output_type, fact_sheet, job_settings, **kwargs)

    monkeypatch.setattr(runner, "generate_output", flaky)
    created = client.post("/api/jobs", data={"text": "Short test source text.", "outputs": ["x_thread", "linkedin_post"]}).json()
    job = wait_for(created["id"])
    assert job["status"] == "ready"  # one output worked
    assert [o["status"] for o in job["outputs"]] == ["done", "failed"]
    assert "took too long" in job["outputs"][1]["error"]
    first_x_thread_finish = job["outputs"][0]["finished_at"]

    monkeypatch.setattr(runner, "generate_output", real_generate)
    assert client.post(f"/api/jobs/{created['id']}/retry").status_code == 200
    job = wait_for(created["id"])
    assert [o["status"] for o in job["outputs"]] == ["done", "done"]
    assert job["outputs"][0]["finished_at"] == first_x_thread_finish  # the finished output was not redone
    assert job["error"] is None


def test_fact_sheet_failure_fails_the_job(monkeypatch):
    def broken(*args, **kwargs):
        raise llm.LLMError("Could not reach the local AI server.")

    monkeypatch.setattr(runner, "build_fact_sheet", broken)
    created = client.post("/api/jobs", data={"text": "Some source text here.", "outputs": ["x_thread"]}).json()
    job = wait_for(created["id"])
    assert job["status"] == "failed"
    assert "Could not reach" in job["error"]
    assert job["fact_sheet"] is None
