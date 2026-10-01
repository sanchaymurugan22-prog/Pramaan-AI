"""Stage 9B part 3: line comments by Reviewers (separation of duties, only while in review, taken back but
never deleted), send-back reasons, and the Reviewer dashboard's numbers."""

import uuid

from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "comments.operator")
reviewer = signed_in_client("reviewer", "comments.reviewer")
second = signed_in_client("reviewer", "comments.second")


def submitted_job() -> dict:
    job = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8") + uuid.uuid4().hex,
                                           "outputs": ["x_thread", "advisory"]}).json()
    done = wait_for(job["id"])
    assert operator.post(f"/api/jobs/{done['id']}/submit", json={}).status_code == 200
    return operator.get(f"/api/jobs/{done['id']}").json()


def first_sentence(job: dict) -> tuple[dict, dict]:
    output = next(o for o in job["outputs"] if o["type"] == "advisory")
    sentence = next(s for s in output["quality"]["sentences"] if s["status"] == "linked")
    return output, sentence


def test_comment_on_a_sentence_then_send_back_with_reasons():
    job = submitted_job()
    url = f"/api/jobs/{job['id']}"
    output, sentence = first_sentence(job)
    form = {"output_id": output["id"], "sentence_id": sentence["id"], "path": sentence["path"], "quote": sentence["text"],
            "text": "This district is not in the source. Please recheck."}
    made = reviewer.post(f"{url}/comments", json=form)
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["output_label"] == "Advisory" and body["author"] == "Comments Reviewer" and body["job_version"] == 1

    # the Operator cannot comment, and sees the comment
    assert operator.post(f"{url}/comments", json=form).status_code == 403
    assert [c["id"] for c in operator.get(f"{url}/comments").json()] == [body["id"]]
    # only its author can take it back
    assert second.delete(f"{url}/comments/{body['id']}").status_code == 403
    extra = reviewer.post(f"{url}/comments", json=form | {"text": "Second thought"}).json()
    assert reviewer.delete(f"{url}/comments/{extra['id']}").status_code == 200
    assert len(operator.get(url).json()["comments"]) == 1  # taken back: not shown (kept in the database)

    # unknown reasons are refused; a send-back with comments needs no note
    assert reviewer.post(f"{url}/review", json={"decision": "send_back", "reasons": ["Bad vibes"]}).status_code == 400
    sent = reviewer.post(f"{url}/review", json={"decision": "send_back", "reasons": ["Facts need checking", "Tone"]})
    assert sent.status_code == 200, sent.text
    notes = sent.json()["reviews"][-1]["notes"]
    assert notes == "Reasons: Facts need checking, Tone."
    note = next(n for n in operator.get("/api/notifications").json()["items"] if n["job_id"] == job["id"])
    assert note["kind"] == "sent_back" and "1 line comment" in note["detail"]

    # after the review: no more comments, and they cannot be taken back
    assert reviewer.post(f"{url}/comments", json=form).status_code == 409
    assert reviewer.delete(f"{url}/comments/{body['id']}").status_code == 409


def test_send_back_still_needs_a_note_or_a_comment():
    job = submitted_job()
    refused = reviewer.post(f"/api/jobs/{job['id']}/review", json={"decision": "send_back", "notes": ""})
    assert refused.status_code == 400 and "line" in refused.json()["detail"]


def test_someone_who_worked_on_the_job_cannot_comment():
    job = submitted_job()
    # an Operator who later became a Reviewer (made the job) is still refused
    from app.db import SessionLocal, User
    with SessionLocal() as db:
        user = db.query(User).filter_by(username="comments.operator").one()
        user.role = "reviewer"
        db.commit()
    try:
        refused = operator.post(f"/api/jobs/{job['id']}/comments", json={"text": "Looks fine to me"})
        assert refused.status_code == 403 and "separation" in refused.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.query(User).filter_by(username="comments.operator").update({"role": "operator"})
            db.commit()


def test_dashboard_numbers():
    job = submitted_job()
    queue = reviewer.get("/api/review/queue").json()
    assert queue["stats"]["waiting"] >= 1 and queue["stats"]["oldest_submitted_at"]
    assert queue["signer"]["ready"] and queue["signer"]["holder"] == "Comments Reviewer"
    assert "Formatting" in queue["reasons"]
    item = next(i for i in queue["waiting"] if i["id"] == job["id"])
    assert item["languages"] == ["en"] and item["leaks"] == 0
    approved = reviewer.post(f"/api/jobs/{job['id']}/review", json={"decision": "approve"}).json()
    after = reviewer.get("/api/review/queue").json()
    assert after["stats"]["signed_today"] >= 1 and after["stats"]["files_in_last_kit"] >= 1
    assert after["signed_today"][0]["record_no"] == approved["record"]["record_no"]
    assert after["stats"]["average_review_minutes"] is not None
