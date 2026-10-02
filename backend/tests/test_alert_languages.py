"""Stage 8 part 5: the emergency alert in many languages. The SMS is an output written by the Operator; it is
translated like every output, kept within the SMS length (160 / 70 characters), checked, ticked by a native
speaker, signed, and comes with a voice announcement where a voice exists."""

from tests.auth_helpers import signed_in_client
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "alertlang.operator")
reviewer = signed_in_client("reviewer", "alertlang.reviewer")

MESSAGE = "Cyber alert: Do not open unknown links about hospital bills. Report fraud by calling 1930."


def by(job, output_type, language):
    return next(o for o in job["outputs"] if o["type"] == output_type and o["language"] == language)


def test_preview_in_every_language():
    preview = operator.post("/api/alerts/preview", json={"message": MESSAGE, "languages": ["ta", "hi", "ur"]})
    assert preview.status_code == 200, preview.text
    cards = preview.json()["languages"]
    assert [c["code"] for c in cards] == ["hi", "ta", "ur"]
    hindi = cards[0]
    assert hindi["text"].startswith("हिन्दी · ") and hindi["limit"] == 70 and hindi["changed"] == []
    assert hindi["sms_parts"] == 2 and hindi["voice"] == "Test tone"
    assert cards[1]["voice"] is None and cards[2]["rtl"] is True
    bad = operator.post("/api/alerts/preview", json={"message": MESSAGE, "languages": ["xx"]})
    assert bad.status_code == 400


def alert(languages, voice=True) -> dict:
    response = operator.post("/api/alerts", json={"type": "Cyber fraud", "severity": "Warning", "message": MESSAGE,
                                                  "outputs": ["x_thread"], "languages": languages, "voice": voice})
    assert response.status_code == 201, response.text
    return wait_for(response.json()["id"])


def test_the_sms_is_an_output_in_every_language():
    job = alert(["hi", "ta"])
    assert job["status"] == "in_review"  # fast-track: to the Reviewers by itself
    english, hindi, tamil = by(job, "sms", "en"), by(job, "sms", "hi"), by(job, "sms", "ta")
    assert english["content"]["message"]["text"] == MESSAGE and english["origin_label"] == "Written by the Operator"
    assert hindi["content"]["message"]["text"] == "हिन्दी · " + MESSAGE
    assert hindi["quality"]["translation"]["changed"] == []  # 1930 survived
    assert english["formats"] == hindi["formats"] == ["txt", "mp3"] and tamil["formats"] == ["txt"]
    assert {o["type"] for o in job["outputs"]} == {"sms", "x_thread"}
    rule = next(r for r in hindi["quality"]["format_rules"] if "SMS" in r["rule"])
    assert rule["ok"]

    announcement = operator.get(f"/api/jobs/{job['id']}/outputs/{hindi['id']}/download", params={"format": "mp3"})
    assert announcement.status_code == 200 and announcement.headers["content-type"] == "audio/mpeg"
    text = operator.get(f"/api/jobs/{job['id']}/outputs/{tamil['id']}/download", params={"format": "txt"})
    assert "தமிழ் · Cyber alert" in text.text

    # one click: every translation ticked (each recorded), then approved and signed with every file
    url = f"/api/jobs/{job['id']}"
    refused = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert refused.status_code == 409
    assert operator.post(f"{url}/native-check-all").status_code == 403
    ticked = reviewer.post(f"{url}/native-check-all")
    assert ticked.status_code == 200
    assert all(o["translation"]["native_check"]["checked"] for o in ticked.json()["outputs"] if o["language"] != "en")
    approved = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    files = {f["name"] for f in approved.json()["record"]["files"]}
    assert {f"job{job['id']}-sms.txt", f"job{job['id']}-sms.mp3", f"job{job['id']}-sms-hi.mp3",
            f"job{job['id']}-sms-ta.txt"} <= files
    assert f"job{job['id']}-sms-ta.mp3" not in files  # no voice for Tamil: text only
    kit = operator.get(f"{url}/kit.zip")
    assert kit.status_code == 200 and kit.headers["content-type"] == "application/zip"


def test_voice_announcement_can_be_switched_off():
    job = alert(["hi"], voice=False)
    assert by(job, "sms", "hi")["formats"] == ["txt"] and by(job, "sms", "en")["formats"] == ["txt"]


def test_the_sms_belongs_to_the_alert_screen():
    options = operator.get("/api/options").json()
    assert "sms" not in [o["key"] for o in options["output_types"]]
    refused = operator.post("/api/jobs", data={"text": MESSAGE + " " * 30, "outputs": ["sms"]})
    assert refused.status_code == 400
