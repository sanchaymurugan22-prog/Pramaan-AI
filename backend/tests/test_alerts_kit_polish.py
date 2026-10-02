"""Stage 9A part 4: Emergency alert (public-release check, fast-track review), choosing what goes in the
campaign kit, and polish (mock captions that read well, long titles in file footers)."""

import io
import zipfile

import docx
import pypdf

from app.ai.mock_ai import SMALL_WORDS, _caption
from app.exporters.common import fit_title
from app.safety.public_check import check_public_text
from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "alert.operator")
reviewer = signed_in_client("reviewer", "alert.reviewer")
CALM = "Cyber alert: Do not open unknown links about hospital bills. Report fraud by calling 1930."


def test_public_release_check():
    assert check_public_text(CALM) == {"ok": True, "problems": []}  # 1930 is a helpline, not private data
    panic = check_public_text("Deadly virus in your phone! Forward this to everyone now.")
    assert not panic["ok"] and {p["kind"] for p in panic["problems"]} == {"panic"}
    assert check_public_text("DO NOT OPEN THESE LINKS today")["problems"][0]["kind"] == "shouting"
    assert check_public_text("Report fraud to CERT-IN by SMS and OTP")["ok"]  # acronyms are not shouting
    assert check_public_text("Really!! Report it.")["problems"][0]["label"] == "Many exclamation marks"
    private = check_public_text("Call Ramesh on 98765 43210 to report fraud.")
    assert [p["kind"] for p in private["problems"]] == ["private"]


def test_alert_check_counts_sms_characters():
    body = operator.post("/api/alerts/check", json={"message": CALM}).json()
    assert body["chars"] == len(CALM) and body["sms_parts"] == 1 and body["fits_one_sms"] and body["ok"]
    long = operator.post("/api/alerts/check", json={"message": CALM * 3}).json()
    assert long["sms_parts"] == 2 and not long["fits_one_sms"]


def test_an_alert_goes_to_fast_track_review_by_itself():
    response = operator.post("/api/alerts", json={"type": "Cyber fraud", "severity": "Warning", "message": CALM})
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["created_via"] == "emergency" and job["tlp"] == "CLEAR"
    assert job["alert"]["message"] == CALM and job["alert"]["sms_parts"] == 1
    assert sorted(o["type"] for o in job["outputs"]) == ["infographic", "sms", "x_thread"]  # Stage 8: + the SMS
    assert job["sources"][0]["filename"] == "emergency-alert.txt"

    done = wait_for(job["id"])
    assert done["status"] == "in_review", done["error"]
    assert done["reviews"][0]["notes"] == "Emergency alert: fast-track review"
    queue = reviewer.get("/api/review/queue").json()["waiting"]
    position = [q["id"] for q in queue].index(job["id"])
    assert all(q["fast_track"] for q in queue[: position + 1])  # emergency alerts come first (other tests' alerts too)
    notes = reviewer.get("/api/notifications").json()["items"]
    assert any(n["kind"] == "alert" and n["job_id"] == job["id"] for n in notes)
    # the Reviewer still decides: approving signs it as usual
    approved = reviewer.post(f"/api/jobs/{job['id']}/review", json={"decision": "approve"})
    assert approved.status_code == 200 and approved.json()["record"]["record_no"]


def test_alerts_that_fail_the_check_are_refused():
    def post(**fields):
        return operator.post("/api/alerts", json={"type": "Flood", "severity": "Warning", "message": CALM} | fields)

    assert post(message="PANIC! Deadly floods will destroy everything, forward this to everyone").status_code == 400
    assert "public-release check" in post(message="Call Ramesh on 98765 43210 about the flood relief.").json()["detail"]
    assert post(type="Earthquake").status_code == 400
    assert post(message="Too short").status_code == 400
    assert post(outputs=["advisory"]).status_code == 400  # internal outputs are not for public alerts


def test_kit_with_some_outputs_and_kit_info():
    response = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": ["x_thread", "executive_summary"]})
    job = wait_for(response.json()["id"])
    url = f"/api/jobs/{job['id']}"
    info = operator.get(f"{url}/kit-info").json()
    assert [o["type"] for o in info["outputs"]] == ["x_thread", "executive_summary"]
    assert all(f["bytes"] is None for o in info["outputs"] for f in o["files"])  # sizes are known once signed

    names = zipfile.ZipFile(io.BytesIO(operator.get(f"{url}/kit.zip?outputs=x_thread").content)).namelist()
    assert any("x-thread" in n or "x_thread" in n for n in names)
    assert not any("executive" in n for n in names)
    assert operator.get(f"{url}/kit.zip?outputs=video_package").status_code == 400

    operator.post(f"{url}/submit", json={})
    reviewer.post(f"{url}/review", json={"decision": "approve"})
    signed = operator.get(f"{url}/kit-info").json()
    assert signed["record"]["record_no"] and all(f["bytes"] > 0 for o in signed["outputs"] for f in o["files"])
    signed_names = zipfile.ZipFile(io.BytesIO(operator.get(f"{url}/kit.zip?outputs=executive_summary").content)).namelist()
    assert "record.json" in signed_names and not any("x-thread" in n or "x_thread" in n for n in signed_names)


def test_mock_captions_read_as_phrases():
    assert _caption("The attackers enter through an unpatched remote-access gateway, tracked here as CVE-1.", 6) == \
        "The attackers enter"
    assert _caption("As of 28 September, 42 hospitals in five states have reported disruption.", 6) == \
        "42 hospitals in five states"
    assert _caption("Apply the vendor's September patch to every remote-access gateway today.", 6) == \
        "Apply the vendor's September patch"
    assert _caption("Hospitals that did", 6) == "Hospitals"  # never ends on a small word
    assert _caption("Short and whole.", 6) == "Short and whole"

    response = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": ["video_package", "presentation"]})
    job = wait_for(response.json()["id"])
    video = next(o for o in job["outputs"] if o["type"] == "video_package")["content"]
    for scene in video["scenes"]:
        assert scene["on_screen_text"].split()[-1].lower() not in SMALL_WORDS, scene["on_screen_text"]
    slides = next(o for o in job["outputs"] if o["type"] == "presentation")["content"]["slides"]
    for bullet in (b for s in slides for b in s["bullets"]):
        assert bullet.split()[-1].lower() not in SMALL_WORDS, bullet


def test_long_titles_fit_in_file_footers():
    assert fit_title("Job #1: ", "A very long title that goes on and on", " · Page 1", len, 30) == "Job #1: A very long… · Page 1"
    title = "Ransomware attack on hospital networks in five states with a very long descriptive title that keeps going"
    response = operator.post("/api/jobs", data={"title": title, "text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": ["executive_summary"]})
    job = wait_for(response.json()["id"])
    output = job["outputs"][0]
    base = f"/api/jobs/{job['id']}/outputs/{output['id']}/download?format="

    pdf = pypdf.PdfReader(io.BytesIO(operator.get(base + "pdf").content))
    job_line = next(line for line in pdf.pages[0].extract_text().splitlines() if line.startswith(f"Job #{job['id']}:"))
    assert "…" in job_line and job_line.endswith("Page 1") and title not in job_line

    document = docx.Document(io.BytesIO(operator.get(base + "docx").content))
    footer = document.sections[0].footer.paragraphs[0].text
    assert "…" in footer and title not in footer and footer.startswith("AI-assisted")
