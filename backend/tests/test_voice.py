"""Stage 8 part 4: voice. Narration (.mp3) and video (.mp4) of the video package, "Read results aloud", and a
recording as a source (speech-to-text). Mock voice and mock speech-to-text; tests/test_real_models.py tries the
real ones."""

import io
import wave

from app.lang import tts
from app.lang.audio import to_wav
from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "voice.operator")
reviewer = signed_in_client("reviewer", "voice.reviewer")


def video_job(languages=("hi", "ta")) -> dict:
    response = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                                "outputs": ["video_package"], "languages": list(languages)})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready"
    return done


def output(job, language) -> dict:
    return next(o for o in job["outputs"] if o["type"] == "video_package" and o["language"] == language)


def get(job, out, fmt):
    return operator.get(f"/api/jobs/{job['id']}/outputs/{out['id']}/download", params={"format": fmt})


def test_narration_and_video_where_a_voice_exists():
    job = video_job()
    english, hindi, tamil = output(job, "en"), output(job, "hi"), output(job, "ta")
    assert english["formats"] == hindi["formats"] == ["docx", "srt", "mp3", "mp4"]
    assert tamil["formats"] == ["docx", "srt", "mp4"]  # no voice for Tamil: no narration, a silent video

    mp3 = get(job, hindi, "mp3")
    assert mp3.status_code == 200 and mp3.headers["content-type"] == "audio/mpeg" and len(mp3.content) > 1000
    assert mp3.headers["content-disposition"].endswith('-video-package-hi.mp3"')
    seconds = _seconds(mp3.content)
    words = sum(len(s["narration"].split()) for s in hindi["content"]["scenes"])
    assert seconds > words / 2.5  # the narration is all there (mock voice: 2.5 words a second, plus pauses)

    mp4 = get(job, hindi, "mp4")
    assert mp4.status_code == 200 and mp4.content[4:8] == b"ftyp"
    assert abs(_seconds(mp4.content) - seconds) < 4  # the video is as long as the narration (+ closing picture)

    silent = get(job, tamil, "mp4")
    assert silent.status_code == 200 and silent.content[4:8] == b"ftyp"
    no_voice = get(job, tamil, "mp3")
    assert no_voice.status_code == 400 and "not available for Tamil" in no_voice.json()["detail"]


def _seconds(media: bytes) -> float:
    with wave.open(io.BytesIO(to_wav(media))) as w:
        return w.getnframes() / w.getframerate()


def test_signed_kit_has_the_video():
    job = video_job(languages=("hi",))
    url = f"/api/jobs/{job['id']}"
    assert operator.post(f"{url}/submit", json={}).status_code == 200
    hindi = output(job, "hi")
    reviewer.post(f"{url}/outputs/{hindi['id']}/native-check", json={"checked": True})
    approved = reviewer.post(f"{url}/review", json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    files = {f["name"] for f in approved.json()["record"]["files"]}
    assert {f"job{job['id']}-video-package.mp4", f"job{job['id']}-video-package-hi.mp4",
            f"job{job['id']}-video-package-hi.mp3"} <= files


def test_read_results_aloud():
    job = video_job(languages=("ta",))
    english, tamil = output(job, "en"), output(job, "ta")
    heard = operator.get(f"/api/jobs/{job['id']}/outputs/{english['id']}/listen")
    assert heard.status_code == 200 and heard.headers["content-type"] == "audio/mpeg"
    silent = operator.get(f"/api/jobs/{job['id']}/outputs/{tamil['id']}/listen")
    assert silent.status_code == 409 and "not available for Tamil" in silent.json()["detail"]
    saved = operator.put("/api/profile", json={"prefs": {"read_aloud": True}})
    assert saved.status_code == 200 and saved.json()["user"]["prefs"]["read_aloud"] is True


def test_a_recording_as_a_source():
    recording, _ = tts.speak("A short recorded briefing from the cyber cell about a ransomware attack.", "en")
    response = operator.post("/api/jobs", data={"audio_language": "hi"},
                             files={"files": ("briefing.wav", recording, "audio/wav")})
    assert response.status_code == 201, response.text
    job = response.json()
    source = job["sources"][0]
    assert source["kind"] == "audio" and source["filename"] == "briefing.wav"
    assert source["transcript"]["model"] == "Mock speech-to-text" and source["transcript"]["language"] == "hi"
    assert source["transcript"]["seconds"] > 3
    text = operator.get(f"/api/jobs/{job['id']}/sources/S1").json()["pages"][0]
    assert "42 hospitals" in text  # the mock transcript
    assert job["status"] == "draft" and job["safety"]["checked"]["sources"] == 1  # the safety check comes next


def test_recordings_that_cannot_be_used():
    recording, _ = tts.speak("A short briefing.", "en")
    wrong = operator.post("/api/jobs", data={"audio_language": "bn"}, files={"files": ("b.mp3", recording, "audio/mpeg")})
    assert wrong.status_code == 400 and "Hindi, Tamil, English" in wrong.json()["detail"]
    broken = operator.post("/api/jobs", data={"audio_language": "hi"}, files={"files": ("b.mp3", b"not sound", "audio/mpeg")})
    assert broken.status_code == 400 and "could not be read" in broken.json()["detail"]
    other = operator.post("/api/jobs", files={"files": ("notes.xyz", b"hello", "text/plain")})
    assert other.status_code == 400 and "recording" in other.json()["detail"]
