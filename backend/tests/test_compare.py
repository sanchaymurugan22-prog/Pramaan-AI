"""Stage 9A part 3: version compare. v1 (what the reviewer saw) against v2 (after the changes), word by word,
with the numbers and lists that changed."""

from app.pipeline.compare import amounts, number_changes, word_diff
from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "compare.operator")
reviewer = signed_in_client("reviewer", "compare.reviewer")


def finished_job() -> dict:
    response = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": ["x_thread", "advisory"]})
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready", done["error"]
    return done


def edit(job: dict, output_type: str, path: list, text: str) -> dict:
    output = next(o for o in job["outputs"] if o["type"] == output_type)
    response = operator.put(f"/api/jobs/{job['id']}/outputs/{output['id']}", json={"fields": [{"path": path, "text": text}]})
    assert response.status_code == 200, response.text
    return response.json()


def test_word_diff_marks_removed_and_added_words():
    left, right = word_diff("42 hospitals across five states", "57 hospitals across six states")
    assert [p for p in left if p["kind"] == "removed"] == [{"text": "42", "kind": "removed"}, {"text": "five", "kind": "removed"}]
    assert [p["text"] for p in right if p["kind"] == "added"] == ["57", "six"]
    assert "".join(p["text"] for p in left) == "42 hospitals across five states"  # nothing lost
    assert word_diff("same text", "same text") == ([{"text": "same text", "kind": "same"}],) * 2


def test_number_changes_understand_words_and_skip_dates():
    assert amounts(["42 hospitals in five states since 22 September 2026"]) == {"hospitals": {"42"}, "states": {"5"}}
    changes = number_changes(["42 hospitals in five states"], ["57 hospitals in six states"])
    assert changes == [{"label": "Hospitals", "before": "42", "after": "57"},
                       {"label": "States", "before": "5", "after": "6"}]
    assert number_changes(["seen on 22 September"], ["seen on 24 September"]) == []


def test_version_1_against_version_2_after_sent_back():
    job = finished_job()
    url = f"/api/jobs/{job['id']}"
    tweet = next(o for o in job["outputs"] if o["type"] == "x_thread")["content"]["tweets"][2]["text"]
    assert "42 hospitals in five states" in tweet

    # only one version yet: the first AI draft against version 1
    first = operator.get(f"{url}/compare").json()
    assert [v["key"] for v in first["versions"]] == [0, 1]
    assert first["left"]["key"] == 0 and first["right"]["key"] == 1
    assert first["summary"]["outputs_changed"] == 0

    operator.post(f"{url}/submit", json={})
    reviewer.post(f"{url}/review", json={"decision": "send_back", "notes": "New numbers came in"})
    changed = edit(job, "x_thread", ["tweets", 2, "text"], tweet.replace("42 hospitals in five states", "57 hospitals in six states"))
    advisory = next(o for o in changed["outputs"] if o["type"] == "advisory")
    recommendations = advisory["content"]["recommendations"]
    edit(changed, "advisory", ["recommendations", len(recommendations) - 1, "text"], "")  # one action removed
    operator.post(f"{url}/submit", json={})  # goes back as v2

    body = reviewer.get(f"{url}/compare").json()
    assert [v["key"] for v in body["versions"]] == [0, 1, 2]
    assert body["left"]["key"] == 1 and body["left"]["status"] == "sent back"
    assert body["right"]["key"] == 2 and body["right"]["status"] == "in review"
    summary = body["summary"]
    assert summary["outputs_changed"] == 2 and summary["outputs"] == 2
    assert {"label": "Hospitals", "before": "42", "after": "57"} in summary["numbers"]
    assert {"label": "States", "before": "5", "after": "6"} in summary["numbers"]
    assert {"label": "Recommended actions", "before": len(recommendations), "after": len(recommendations) - 1,
            "output": "Advisory"} in summary["lists"]

    thread = next(o for o in body["outputs"] if o["type"] == "x_thread")
    assert thread["left"]["version"] == 1 and thread["right"]["version"] == 2
    post = next(f for f in thread["fields"] if f["path"] == ["tweets", 2, "text"])
    assert post["changed"] and {"text": "57", "kind": "added"} in post["right"]
    assert {"text": "42", "kind": "removed"} in post["left"]
    unchanged = next(f for f in thread["fields"] if f["path"] == ["tweets", 0, "text"])
    assert not unchanged["changed"]

    # pick the versions yourself; unknown versions are refused
    again = operator.get(f"{url}/compare?left=0&right=1").json()
    assert again["summary"]["outputs_changed"] == 0  # v1 was exactly the AI draft
    assert operator.get(f"{url}/compare?left=7&right=2").status_code == 404
