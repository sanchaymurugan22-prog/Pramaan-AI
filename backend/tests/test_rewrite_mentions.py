"""Stage 8 extras from the designs: the "Shorter / More formal / Simpler" buttons on the Results page (design 14)
and the "Mentions" tab of Notifications (design 40): a Reviewer names someone with @ in a comment."""

import uuid

from tests.auth_helpers import make_user, signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "rewrite.operator")
reviewer = signed_in_client("reviewer", "rewrite.reviewer")


def job_with(outputs, languages=()) -> dict:
    response = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8") + uuid.uuid4().hex,
                                                "outputs": outputs, "languages": list(languages)})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready"
    return done


def by(job, output_type, language="en"):
    return next(o for o in job["outputs"] if o["type"] == output_type and o["language"] == language)


def words(content) -> str:
    """Every text of an output, joined (fact ids and hashtags left out)."""
    if isinstance(content, str):
        return content + " "
    if isinstance(content, list):
        return "".join(words(v) for v in content)
    if isinstance(content, dict):
        return "".join(words(v) for k, v in content.items() if k not in ("fact_ids", "hashtags", "indicators"))
    return ""


def rewrite(job, output, change):
    response = operator.post(f"/api/jobs/{job['id']}/outputs/{output['id']}/rewrite", json={"change": change})
    assert response.status_code == 200, response.text
    return wait_for(job["id"])


def test_shorter_keeps_the_facts_and_makes_a_new_version():
    job = job_with(["executive_summary"], languages=["hi"])
    before = by(job, "executive_summary")
    after = by(rewrite(job, before, "shorter"), "executive_summary")
    assert after["version"] == before["version"] + 1 and after["origin_label"] == "Made shorter by AI"
    assert len(words(after["content"])) < len(words(before["content"]))
    assert after["quality"]["sentences"] and all(s["status"] != "unsupported" for s in after["quality"]["sentences"]
                                                 if s.get("fact_ids"))
    # the old text is kept as an older version; the translation is made again from the new English
    versions = operator.get(f"/api/jobs/{job['id']}/outputs/{after['id']}/versions").json()
    assert sorted(v["origin"] for v in versions) == ["ai", "shorter"]
    done = wait_for(job["id"])
    hindi = by(done, "executive_summary", "hi")
    assert hindi["translation"]["source_version"] == after["version"]


def test_more_formal_and_simpler():
    job = job_with(["advisory"])
    formal = by(rewrite(job, by(job, "advisory"), "formal"), "advisory")
    assert formal["origin_label"] == "Made more formal by AI" and "!" not in words(formal["content"])
    simpler = by(rewrite(job, formal, "simpler"), "advisory")
    text = words(simpler["content"])
    assert simpler["origin_label"] == "Made simpler by AI" and "unpatched" not in text and "out-of-date" in text
    # numbers and indicators are never touched
    assert "42 hospitals" in text and simpler["content"]["indicators"] == formal["content"]["indicators"]


def test_rewrite_refusals():
    job = job_with(["x_thread"], languages=["ta"])
    url = f"/api/jobs/{job['id']}/outputs"
    english, tamil = by(job, "x_thread"), by(job, "x_thread", "ta")
    assert operator.post(f"{url}/{english['id']}/rewrite", json={"change": "funnier"}).status_code == 400
    refused = operator.post(f"{url}/{tamil['id']}/rewrite", json={"change": "shorter"})
    assert refused.status_code == 400 and "English" in refused.json()["detail"]
    assert reviewer.post(f"{url}/{english['id']}/rewrite", json={"change": "shorter"}).status_code == 403


def test_a_mention_notifies_that_person():
    priya = make_user("mention.priya", "operator", full_name="Priyanka Testwala", employee_id="EMP-77001")
    second = make_user("mention.second", "reviewer", full_name="Zorawar Mentionsingh")
    job = job_with(["advisory"])
    url = f"/api/jobs/{job['id']}"
    assert operator.post(f"{url}/submit", json={}).status_code == 200
    output = by(job, "advisory")
    made = reviewer.post(f"{url}/comments", json={
        "output_id": output["id"],
        "text": "@Priyanka please check this date. Also @EMP-77001 and @zorawar.mentionsingh; not mail@example.com"})
    assert made.status_code == 201, made.text
    assert made.json()["mentioned"] == ["Priyanka Testwala", "Zorawar Mentionsingh"]

    priya_client = signed_in_client("operator", "mention.priya")
    mentions = priya_client.get("/api/notifications", params={"mentions": "true"}).json()["items"]
    assert len(mentions) == 1  # named twice, told once
    note = mentions[0]
    assert note["kind"] == "mention" and note["job_id"] == job["id"]
    assert note["title"].startswith("Rewrite Reviewer mentioned you") and "Advisory: @Priyanka" in note["detail"]
    assert all(n["kind"] == "mention" for n in mentions)
    # not mentioned: nothing on the Mentions tab
    assert operator.get("/api/notifications", params={"mentions": "true"}).json()["items"] == []
    assert second.id and signed_in_client("reviewer", "mention.second").get(
        "/api/notifications", params={"mentions": "true"}).json()["items"]
