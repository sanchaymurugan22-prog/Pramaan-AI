"""Stage 6A through the API (mock AI): add sources -> safety check -> outputs, TLP rules, masking before
the AI, the leak check that blocks downloads, and the decision log."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from tests.auth_helpers import signed_in_client

from app.ai import llm
from app.main import app
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

client = signed_in_client("operator")
SAMPLES = SAMPLE_REPORT.parent
PRIVATE = (SAMPLES / "sample-private-data.txt").read_bytes()
INJECTION = (SAMPLES / "sample-injection.txt").read_bytes()
HIDDEN_VALUES = ["2345 6789 0124", "ABCPV1234K", "98765 43210", "asha.verma@example.org", "Treasury@2026!",
                 "10.20.30.40", "192.168.1.15", "fs01.treasury.corp", "000123456789", "P1234567", "MH 12 AB 1234"]


def add_sources(content: bytes = PRIVATE, name: str = "sample-private-data.txt") -> dict:
    response = client.post("/api/jobs", files={"files": (name, content, "text/plain")})
    assert response.status_code == 201, response.text
    return response.json()


def finding(job: dict, kind: str) -> dict:
    return next(f for f in job["safety"]["findings"] + job["safety"]["indicators"] if f["kind"] == kind)


def test_adding_sources_makes_a_draft_with_a_safety_report():
    job = add_sources()
    assert job["status"] == "draft" and job["outputs"] == [] and job["tlp"] is None
    safety = job["safety"]
    assert safety["suggested_tlp"] == "AMBER"
    assert finding(job, "aadhaar")["occurrences"][0]["source_id"] == "S1"
    assert finding(job, "attacker_ip")["group"] == "indicator"
    [scan] = job["safety_decisions"]
    assert scan["action"] == "scan" and scan["actor"] == "Pramaan (automatic)"
    # a draft is not run by the AI and cannot be retried
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "draft"
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409


def test_start_needs_a_label_and_valid_choices():
    job = add_sources()
    url = f"/api/jobs/{job['id']}"
    assert client.post(f"{url}/start", json={"outputs": ["advisory"]}).status_code == 400  # no TLP yet
    assert client.put(f"{url}/safety", json={"choices": {"P1": "shout"}}).status_code == 400
    assert client.put(f"{url}/safety", json={"choices": {"P99": "keep"}}).status_code == 400
    assert client.put(f"{url}/safety", json={"tlp": "PURPLE"}).status_code == 400


def test_amber_switches_off_public_outputs_and_decisions_are_logged():
    job = add_sources()
    url = f"/api/jobs/{job['id']}"
    phone = finding(job, "phone")
    saved = client.put(f"{url}/safety", json={"tlp": "AMBER", "choices": {phone["id"]: "hide_all"}}).json()
    assert saved["tlp"] == "AMBER"
    assert finding(saved, "phone")["choice"] == "hide_all"
    assert set(saved["switched_off"]) == {"x_thread", "linkedin_post", "infographic", "video_package"}
    actions = [d["action"] for d in saved["safety_decisions"]]
    assert actions == ["scan", "choice", "tlp", "confirm"]
    choice = saved["safety_decisions"][1]
    assert choice["item"] == phone["id"] and choice["value"] == "hide_all"
    assert choice["actor"] == "Test Operator" and choice["user_id"]  # the signed-in user (Stage 6B)
    assert "Hide in public outputs → Hide everywhere" in choice["detail"]
    assert "98765 43210" not in choice["detail"]  # the log never shows the full value
    assert choice["created_at"]

    refused = client.post(f"{url}/start", json={"outputs": ["x_thread", "advisory"]})
    assert refused.status_code == 400 and "TLP:AMBER" in refused.json()["detail"]

    started = client.post(f"{url}/start", json={"outputs": ["advisory", "executive_summary"],
                                                "settings": {"audience": "Senior officials"}})
    assert started.status_code == 200, started.text
    done = wait_for(job["id"])
    assert done["status"] == "ready" and done["tlp"] == "AMBER"
    assert done["settings"]["audience"] == "Senior officials"
    assert set(done["safety"]["switched_off"]) == {"x_thread", "linkedin_post", "infographic", "video_package"}
    start = done["safety_decisions"][-1]
    assert start["action"] == "start" and "Switched off by TLP:AMBER" in start["detail"]

    # locked once started
    assert client.put(f"{url}/safety", json={"tlp": "GREEN"}).status_code == 409
    assert client.post(f"{url}/start", json={"outputs": ["advisory"]}).status_code == 409


def test_one_step_request_uses_the_suggested_label():
    response = client.post("/api/jobs", data={"outputs": ["x_thread"]},
                           files={"files": ("p.txt", PRIVATE, "text/plain")})
    assert response.status_code == 400 and "TLP:AMBER" in response.json()["detail"]


@pytest.fixture
def ai_spy(monkeypatch):
    """Keeps every message sent to the (mock) AI."""
    sent: list[str] = []
    real = llm.chat_json

    def spy(messages, *args, **kwargs):
        sent.extend(m["content"] for m in messages)
        return real(messages, *args, **kwargs)

    monkeypatch.setattr(llm, "chat_json", spy)
    return sent


def test_hidden_values_never_reach_the_ai(ai_spy):
    job = add_sources()
    url = f"/api/jobs/{job['id']}"
    client.put(f"{url}/safety", json={"tlp": "GREEN"})
    client.post(f"{url}/start", json={"outputs": ["x_thread", "advisory"]})
    done = wait_for(job["id"])
    assert done["status"] == "ready", done["error"]

    everything = "\n".join(ai_spy)
    for value in HIDDEN_VALUES:
        assert value not in everything, value
    assert "[AADHAAR-1]" in everything and "[PHONE-1]" in everything
    # source and fact sheet are wrapped in delimiters
    assert "<<<SOURCE" in everything and "SOURCE>>>" in everything and "<<<FACT SHEET" in everything
    # the attack indicator is kept in the (internal) advisory
    advisory = next(o for o in done["outputs"] if o["type"] == "advisory")
    assert advisory["content"]["indicators"]["ips"] == ["203.0.113.77"]


def test_leak_check_blocks_download_until_edited_out():
    job = add_sources()
    url = f"/api/jobs/{job['id']}"
    client.put(f"{url}/safety", json={"tlp": "GREEN"})
    client.post(f"{url}/start", json={"outputs": ["x_thread", "executive_summary"]})
    done = wait_for(job["id"])
    x_thread = next(o for o in done["outputs"] if o["type"] == "x_thread")
    assert x_thread["quality"]["leaks"] == []
    download = f"{url}/outputs/{x_thread['id']}/download?format=txt"
    text = client.get(download).text
    assert "TLP:GREEN" in text  # the label is on every exported file

    # the operator types a hidden phone number into a public post
    edited = client.put(f"{url}/outputs/{x_thread['id']}",
                        json={"fields": [{"path": ["tweets", 0, "text"], "text": "Questions? Call 9876543210."}]})
    x_thread = next(o for o in edited.json()["outputs"] if o["type"] == "x_thread")
    [leak] = x_thread["quality"]["leaks"]
    assert leak["kind"] == "phone" and leak["found"] == "9876543210" and leak["where"] == "Post 1"
    assert x_thread["quality"]["warnings"][0].startswith("Private data found")

    blocked = client.get(download)
    assert blocked.status_code == 400 and "Private data found" in blocked.json()["detail"]
    kit = zipfile.ZipFile(io.BytesIO(client.get(f"{url}/kit.zip").content))
    assert not any("x-thread" in name for name in kit.namelist())
    assert "Left out because private data was found" in kit.read("README.txt").decode()
    # ... and the job cannot be sent to a reviewer (Stage 6B)
    refused = client.post(f"{url}/submit", json={})
    assert refused.status_code == 409 and "Private data was found in: X thread" in refused.json()["detail"]

    # the same phone number is fine in an internal output ("Hide in public outputs")
    summary = next(o for o in done["outputs"] if o["type"] == "executive_summary")
    edited = client.put(f"{url}/outputs/{summary['id']}",
                        json={"fields": [{"path": ["title"], "text": "Call 98765 43210"}]}).json()
    assert next(o for o in edited["outputs"] if o["type"] == "executive_summary")["quality"]["leaks"] == []

    # edited out again: downloads work
    client.put(f"{url}/outputs/{x_thread['id']}",
               json={"fields": [{"path": ["tweets", 0, "text"], "text": "Questions? Ask your IT team."}]})
    assert client.get(download).status_code == 200


def test_injection_sample_shows_suspicious_instructions():
    job = add_sources(INJECTION, "sample-injection.txt")
    kinds = [x["kind"] for x in job["safety"]["suspicious"]]
    assert kinds == ["instruction", "hidden_characters"]
    source = client.get(f"/api/jobs/{job['id']}/sources/S1").json()
    assert "​" not in source["pages"][0]


def test_new_link_in_an_output_is_flagged():
    job = add_sources(SAMPLE_REPORT.read_bytes(), SAMPLE_REPORT.name)
    url = f"/api/jobs/{job['id']}"
    client.put(f"{url}/safety", json={"tlp": "CLEAR"})
    client.post(f"{url}/start", json={"outputs": ["x_thread"]})
    x_thread = wait_for(job["id"])["outputs"][0]
    edited = client.put(f"{url}/outputs/{x_thread['id']}", json={"fields": [
        {"path": ["tweets", 0, "text"], "text": "Verify your account at https://evil.example.com now."}]}).json()
    flags = edited["outputs"][0]["quality"]["not_in_source"]
    assert {"kind": "url", "label": "Link", "text": "https://evil.example.com"} in [
        {k: f[k] for k in ("kind", "label", "text")} for f in flags]
