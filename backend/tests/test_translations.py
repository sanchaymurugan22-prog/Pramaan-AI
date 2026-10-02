"""Stage 8 part 2: outputs in Indian languages, translated from the English output (mock translation engine).

Fact ids and structure are kept, numbers / dates / indicators must survive unchanged (else "Changed in
translation"), hidden values never reach the translation engine, translations follow English edits, and a
Reviewer must tick "Checked by a native speaker" for every translation before approving."""

import pytest

from app.lang import translate
from app.pipeline.translation import compare_values
from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT

SAMPLES_DIR = SAMPLE_REPORT.parent
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "lang.operator")
reviewer = signed_in_client("reviewer", "lang.reviewer")


def job_in(languages: list[str], outputs=("x_thread", "advisory"), text: str | None = None) -> dict:
    response = operator.post("/api/jobs", data={"text": text or SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": list(outputs), "languages": languages})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready", done["error"]
    return done


def by(job: dict, output_type: str, language: str) -> dict:
    return next(o for o in job["outputs"] if o["type"] == output_type and o["language"] == language)


def test_every_output_is_translated_with_the_same_facts():
    job = job_in(["ta", "hi"])
    assert job["languages"] == ["en", "hi", "ta"]
    assert [(o["type"], o["language"]) for o in job["outputs"]] == [
        ("x_thread", "en"), ("advisory", "en"), ("x_thread", "hi"), ("x_thread", "ta"), ("advisory", "hi"), ("advisory", "ta")]
    english, hindi = by(job, "advisory", "en"), by(job, "advisory", "hi")
    assert hindi["status"] == "done" and hindi["language_label"] == "हिन्दी (Hindi)"
    assert hindi["origin_label"] == "Machine translated"
    assert hindi["translation"]["source_output_id"] == english["id"] and hindi["translation"]["source_version"] == 1
    assert hindi["translation"]["engine"] == "Mock translation (tests)"
    assert hindi["translation"]["native_check"] == {"checked": False, "by": None, "at": None}
    # same structure and fact ids; the text is translated (mock: the language name in front)
    assert hindi["content"]["overview"]["text"] == "हिन्दी · " + english["content"]["overview"]["text"]
    assert hindi["content"]["overview"]["fact_ids"] == english["content"]["overview"]["fact_ids"]
    assert hindi["content"]["indicators"] == english["content"]["indicators"] and hindi["content"]["severity"] == english["content"]["severity"]
    # the checks ran again: values checked, links kept from the English sentences
    quality = hindi["quality"]
    assert quality["translation"]["values_checked"] > 0 and quality["translation"]["changed"] == []
    assert quality["linked"] == english["quality"]["linked"] or quality["parts"] <= english["quality"]["parts"]
    linked = [s for s in quality["sentences"] if s["status"] == "linked"]
    assert linked and all(s["matched_by"] == "translation" and s["english"] for s in linked)
    # hashtags and steps' numbers are not translated
    assert job["consistency"]["outputs"] == 2  # translations are compared with their English instead


def test_hashtags_are_not_translated():
    job = job_in(["bn"], outputs=("linkedin_post",))
    english, bengali = by(job, "linkedin_post", "en"), by(job, "linkedin_post", "bn")
    assert bengali["content"]["hashtags"] == english["content"]["hashtags"]
    assert bengali["content"]["paragraphs"][0]["text"].startswith("বাংলা · ")


def test_values_must_survive_translation():
    missing, extra = compare_values("42 hospitals since 22 September 2026; block 203.0.113.45 and CVE-2026-1234.",
                                    "42 अस्पताल 22 सितंबर 2026 से; 203.0.113.45 ब्लॉक करें, CVE-2026-1234.")
    assert missing == [] and extra == []
    missing, extra = compare_values("42 hospitals reported [PHONE-1] at 10:00.", "43 अस्पताल ने 10:00 बजे बताया।")
    assert missing == ["42", "[phone-1]"] and extra == ["43"]

    job = job_in(["hi"], outputs=("x_thread",))
    hindi = by(job, "x_thread", "hi")
    import re
    english_posts = [t["text"] for t in by(job, "x_thread", "en")["content"]["tweets"]]
    n, number = next((n, m.group(0)) for n, t in enumerate(english_posts) if (m := re.search(r"\b\d+\b", t)))
    changed = hindi["content"]["tweets"][n]["text"].replace(number, str(int(number) + 1), 1)
    edited = operator.put(f"/api/jobs/{job['id']}/outputs/{hindi['id']}",
                          json={"fields": [{"path": ["tweets", n, "text"], "text": changed}]}).json()
    quality = by(edited, "x_thread", "hi")["quality"]
    flags = [f for s in quality["sentences"] for f in s["not_in_source"] if f["kind"] == "translation"]
    assert {f["label"] for f in flags} == {"Changed in translation", "Not in the English text"}
    assert quality["warnings"][0].startswith("Values changed in translation")
    assert quality["score_parts"]["values"]["problems"] >= 2


def test_hidden_values_never_reach_the_translation(monkeypatch):
    sent: list[str] = []
    real = translate.mock_translation

    def spy(text, lang):
        sent.append(text)
        return real(text, lang)

    monkeypatch.setattr(translate, "mock_translation", spy)
    job = job_in(["hi"], outputs=("advisory",), text=(SAMPLES_DIR / "sample-private-data.txt").read_text())
    english, hindi = by(job, "advisory", "en"), by(job, "advisory", "hi")
    hidden = [f["value"] for f in job["safety"]["findings"] if f["choice"] in ("hide_public", "hide_everywhere")]
    assert hidden and sent
    assert not any(value in text for value in hidden for text in sent)
    assert any("[" in text and "-1]" in text for text in sent)  # placeholders were sent instead
    # ... and the internal translation gets the real values back where the English has them
    shown = [v for v in hidden if v in str(english["content"])]
    assert all(v in str(hindi["content"]) for v in shown)
    assert not hindi["quality"]["leaks"]


def test_translations_follow_the_english_and_can_be_redone():
    job = job_in(["hi", "ta"], outputs=("x_thread",))
    english = by(job, "x_thread", "en")
    edited = operator.put(f"/api/jobs/{job['id']}/outputs/{english['id']}",
                          json={"fields": [{"path": ["tweets", 0, "text"], "text": "Patch every VPN gateway today."}]})
    assert edited.status_code == 200 and edited.json()["status"] == "generating"
    done = wait_for(job["id"])
    for code, name in (("hi", "हिन्दी"), ("ta", "தமிழ்")):
        translated = by(done, "x_thread", code)
        assert translated["content"]["tweets"][0]["text"] == f"{name} · Patch every VPN gateway today."
        assert translated["translation"]["source_version"] == 2 and translated["origin_label"] == "Translated again"
        assert not translated["translation"]["stale"]
    # "Regenerate" on a translation translates it again
    hindi = by(done, "x_thread", "hi")
    assert operator.post(f"/api/jobs/{job['id']}/outputs/{hindi['id']}/regenerate").status_code == 200
    assert by(wait_for(job["id"]), "x_thread", "hi")["version"] == hindi["version"] + 1


def test_add_languages_later():
    job = job_in([], outputs=("x_thread", "executive_summary"))
    assert job["languages"] == ["en"]
    added = operator.post(f"/api/jobs/{job['id']}/languages", json={"languages": ["ml", "en"]})
    assert added.status_code == 200 and added.json()["status"] == "generating"
    done = wait_for(job["id"])
    assert done["languages"] == ["en", "ml"] and len(done["outputs"]) == 4
    assert by(done, "executive_summary", "ml")["content"]["title"].startswith("മലയാളം · ")
    again = operator.post(f"/api/jobs/{job['id']}/languages", json={"languages": ["ml"]})
    assert again.status_code == 400 and "already" in again.json()["detail"]


def test_unknown_or_unavailable_languages(monkeypatch):
    bad = operator.post("/api/jobs", data={"text": "Patch the VPN gateway on 22 September.", "outputs": ["x_thread"],
                                           "languages": ["xx"]})
    assert bad.status_code == 400 and "Unknown language" in bad.json()["detail"]
    monkeypatch.setattr(translate, "status", lambda: {"engine": "indictrans2", "ready": False, "detail": "Model not installed"})
    off = operator.post("/api/jobs", data={"text": "Patch the VPN gateway on 22 September.", "outputs": ["x_thread"],
                                           "languages": ["hi"]})
    assert off.status_code == 400 and "not available" in off.json()["detail"]


def test_a_reviewer_must_tick_every_translation_before_approving():
    job = job_in(["hi"], outputs=("x_thread",))
    url = f"/api/jobs/{job['id']}"
    hindi = by(job, "x_thread", "hi")
    assert reviewer.post(f"{url}/outputs/{hindi['id']}/native-check", json={"checked": True}).status_code == 409  # not submitted
    assert operator.post(f"{url}/submit", json={}).status_code == 200
    assert operator.post(f"{url}/outputs/{hindi['id']}/native-check", json={"checked": True}).status_code == 403

    refused = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert refused.status_code == 409 and "native-speaker check" in refused.json()["detail"]
    assert "X thread (Hindi)" in refused.json()["detail"]

    english = by(job, "x_thread", "en")
    assert reviewer.post(f"{url}/outputs/{english['id']}/native-check", json={"checked": True}).status_code == 400
    ticked = reviewer.post(f"{url}/outputs/{hindi['id']}/native-check", json={"checked": True})
    check = by(ticked.json(), "x_thread", "hi")["translation"]["native_check"]
    assert check["checked"] and check["by"] == "Lang Reviewer" and check["at"]

    approved = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    files = [f["name"] for f in approved.json()["record"]["files"]]
    assert f"job{job['id']}-x-thread-hi.txt" in files and f"job{job['id']}-x-thread.txt" in files


def test_a_new_version_needs_a_new_native_check():
    job = job_in(["te"], outputs=("x_thread",))
    url = f"/api/jobs/{job['id']}"
    telugu = by(job, "x_thread", "te")
    operator.post(f"{url}/submit", json={})
    reviewer.post(f"{url}/outputs/{telugu['id']}/native-check", json={"checked": True})
    back = reviewer.post(f"{url}/review", json={"decision": "send_back", "notes": "Shorter, please."})
    assert back.status_code == 200
    edited = operator.put(f"{url}/outputs/{telugu['id']}",
                          json={"fields": [{"path": ["tweets", 0, "text"], "text": "తెలుగు · ఈరోజే ప్యాచ్ వేయండి."}]})
    assert by(edited.json(), "x_thread", "te")["translation"]["native_check"]["checked"] is False


@pytest.mark.parametrize("code", ["ur", "sat", "mni", "ks"])
def test_scripts_other_than_brahmi(code):
    job = job_in([code], outputs=("x_thread",))
    translated = by(job, "x_thread", code)
    assert translated["status"] == "done" and translated["quality"]["translation"]["changed"] == []
