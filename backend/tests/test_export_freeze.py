"""v1.2: exports can never freeze the server.

The bug: asking for the Hindi / Tamil / Urdu infographic (or approving a job, which makes every file) could
stop the whole backend - even /api/health - until it was restarted. The cause was a crash (segfault) inside
FreeType: the first glyph drawn from a font ran FreeType's auto-hinter, which uses its own copy of HarfBuzz,
and that crashed when another thread was shaping text at the same time (a PDF, another image). Under
`uvicorn --reload` (scripts/start.sh) the crashed worker leaves the port open, so every request just waits.

These tests:
  - draw Indian-script images and PDFs in many threads at once in a FRESH Python (fonts not loaded yet, as
    after a restart) - this crashed most runs before the fix;
  - ask a real server (uvicorn, one event loop, as in production) for the hi / ta / ur infographics from
    several threads, each with a time limit, while checking /api/health still answers;
  - check the time limit: a file that takes too long gives a clear 504 error, not a request that never ends.
"""

import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from app import crypto, exporters
from app.config import settings
from app.auth import sessions
from tests.auth_helpers import ORIGIN, signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

BACKEND = Path(__file__).resolve().parents[1]
operator = signed_in_client("operator", "freeze.operator")
reviewer = signed_in_client("reviewer", "freeze.reviewer")


@pytest.fixture(scope="module")
def job():
    response = operator.post("/api/jobs", data={
        "text": SAMPLE_REPORT.read_text(encoding="utf-8"),
        "outputs": ["infographic", "advisory", "executive_summary", "presentation", "linkedin_post", "x_thread",
                    "video_package"], "languages": ["hi", "ta", "ur"]})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"], timeout=30)
    assert done["status"] == "ready"
    return done


def outputs_of(job, output_type: str) -> list[dict]:
    return [o for o in job["outputs"] if o["type"] == output_type and o["language"] in ("hi", "ta", "ur")]


# ---- 1. drawing in many threads at once, in a fresh Python -------------------------------------------------

STRESS = """
import json, random, sys, threading
from app.exporters import _render_now
from app.exporters.common import ExportInfo

work = json.load(open(sys.argv[1]))
random.Random(int(sys.argv[2])).shuffle(work)
errors, lock = [], threading.Lock()

def worker():
    while True:
        with lock:
            if not work:
                return
            item = work.pop()
        try:
            info = ExportInfo(job_id=1, job_title="Freeze test", date="2 Oct 2026", tlp="GREEN",
                              output_type=item["type"], output_label=item["type"], language=item["language"])
            _render_now(info, item["type"], item["content"], item["format"])
        except Exception as exc:  # a Python error is reported; a crash ends the process (exit code -11)
            errors.append(repr(exc))

threads = [threading.Thread(target=worker) for _ in range(6)]
for t in threads: t.start()
for t in threads: t.join()
print("errors:", errors)
sys.exit(1 if errors else 0)
"""


# Real IndicTrans2 translations of the sample report (made by Pramaan AI on 2 Oct 2026). With only the mock
# translation ("हिन्दी · " + English) the crash almost never happened; with these it crashed in about half the runs.
TRANSLATIONS = json.loads((Path(__file__).parent / "fixtures" / "sample-report-translations.json").read_text(encoding="utf-8"))


def test_every_file_in_indian_scripts_made_in_many_threads_at_once(job, tmp_path):
    """Every file of every output (English, Hindi, Tamil, Urdu; not the slow video and voice files), six
    threads at a time, in a fresh Python each run (fonts opened while other threads draw). Before the fix
    this crashed the process (segfault) in most runs; it must finish every time."""
    items = [{"type": o["type"], "language": o["language"], "format": fmt,
              "content": o["content"] if o["language"] == "en" else TRANSLATIONS[o["language"]][o["type"]]}
             for o in job["outputs"] for fmt in exporters.FORMATS[o["type"]] if fmt not in ("mp3", "mp4")]
    assert {i["language"] for i in items} == {"en", "hi", "ta", "ur"} and len(items) >= 40
    work = tmp_path / "work.json"
    work.write_text(json.dumps(items), encoding="utf-8")
    for run in range(5):
        result = subprocess.run([sys.executable, "-c", STRESS, str(work), str(run)], cwd=BACKEND,
                                capture_output=True, text=True, timeout=300)
        assert result.returncode == 0, f"run {run}: exit {result.returncode}\n{result.stdout}\n{result.stderr[-3000:]}"


def test_glyphs_are_never_loaded_with_the_auto_hinter(job, monkeypatch):
    """The crash was in FreeType's auto-hinter (its own copy of HarfBuzz). Drawing never uses it: glyphs are
    loaded unhinted (no difference to see at these sizes), so that code never runs."""
    import freetype

    from app.exporters import shaped
    flags = []
    real = freetype.Face.load_glyph
    monkeypatch.setattr(freetype.Face, "load_glyph", lambda face, index, f=4: (flags.append(f), real(face, index, f))[1])
    for language in ("hi", "ta", "ur"):
        output = next(o for o in outputs_of(job, "infographic") if o["language"] == language)
        info = exporters.ExportInfo(job_id=1, job_title="T", date="2 Oct 2026", tlp=None, output_type="infographic",
                                    output_label="Infographic", language=language)
        exporters._render_now(info, "infographic", TRANSLATIONS[language]["infographic"] | {"layout": "timeline"}, "png")
        exporters._render_now(info, "infographic", output["content"], "png")
    assert flags and all(f & freetype.FT_LOAD_NO_HINTING for f in flags)
    assert shaped._lock.acquire(blocking=False)  # and nothing kept FreeType's lock
    shaped._lock.release()


# ---- 2. a real server: infographics from several threads, health still answers ---------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """The app in a real uvicorn server (one event loop, like scripts/start.sh), in a background thread."""
    from app.main import app
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def _http(base: str, client) -> httpx.Client:
    return httpx.Client(base_url=base, headers=ORIGIN, cookies={sessions.COOKIE_NAME: client.cookies[sessions.COOKIE_NAME]},
                        timeout=60)


def test_indian_infographics_through_http_in_threads(job, live_server):
    results: dict[str, int] = {}

    def fetch(output):
        with _http(live_server, operator) as http:
            response = http.get(f"/api/jobs/{job['id']}/outputs/{output['id']}/download", params={"format": "png"})
            results[f"{output['language']}#{output['id']}"] = response.status_code

    outputs = outputs_of(job, "infographic") * 3  # each language three times, all at once
    threads = [threading.Thread(target=fetch, args=(o,), daemon=True) for o in outputs]
    for t in threads:
        t.start()
    with httpx.Client(base_url=live_server, timeout=5) as http:
        assert http.get("/api/health").status_code == 200  # answers while the images are being made
    for t in threads:
        t.join(timeout=60)
        assert not t.is_alive(), "a download never finished: the server froze"
    assert set(results.values()) == {200}, results
    with httpx.Client(base_url=live_server, timeout=5) as http:
        assert http.get("/api/health").json()["status"] == "ok"


# ---- 3. time limits ------------------------------------------------------------------------------------------

@pytest.fixture
def slow_files(monkeypatch):
    """Every file takes (up to) 30 seconds; release.set() lets them finish."""
    release = threading.Event()

    def slow_writer(info, content, buffer):
        release.wait(30)
        buffer.write(b"late")

    monkeypatch.setattr(exporters, "_writer", lambda output_type, fmt: slow_writer)
    yield release
    release.set()


def test_slow_export_does_not_block_the_server(job, live_server, slow_files):
    output = outputs_of(job, "infographic")[0]
    done = []

    def fetch():
        with _http(live_server, operator) as http:
            done.append(http.get(f"/api/jobs/{job['id']}/outputs/{output['id']}/download", params={"format": "png"}))

    thread = threading.Thread(target=fetch, daemon=True)
    thread.start()
    time.sleep(0.3)  # the file is being made now
    started = time.monotonic()
    with httpx.Client(base_url=live_server, timeout=5) as http:
        assert http.get("/api/health").status_code == 200
    assert time.monotonic() - started < 2
    slow_files.set()
    thread.join(timeout=10)
    assert done and done[0].status_code == 200 and done[0].content == b"late"


def test_export_that_takes_too_long_gives_a_clear_error(job, monkeypatch, slow_files):
    monkeypatch.setattr(settings, "export_timeout_seconds", 0.5)
    output = outputs_of(job, "infographic")[0]
    started = time.monotonic()
    response = operator.get(f"/api/jobs/{job['id']}/outputs/{output['id']}/download", params={"format": "png"})
    assert time.monotonic() - started < 5
    assert response.status_code == 504
    assert "took longer than 0.5 seconds" in response.json()["detail"]


def test_all_workers_busy_gives_a_clear_error(job, monkeypatch, slow_files):
    monkeypatch.setattr(settings, "export_timeout_seconds", 0.5)
    output = outputs_of(job, "infographic")[0]
    url = f"/api/jobs/{job['id']}/outputs/{output['id']}/download"
    # fill every export worker with a slow file, then ask for one more
    for _ in range(settings.export_workers):
        exporters._workers.submit(exporters._render_now, None, "infographic", {}, "png")
    response = operator.get(url, params={"format": "png"})
    assert response.status_code == 504 and "busy" in response.json()["detail"]


def test_signing_that_takes_too_long_signs_nothing(monkeypatch, slow_files):
    """Approving makes every file; if one is too slow, the approval stops with a clear message and the job
    is still waiting for review (nothing half-signed)."""
    created = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"),
                                               "outputs": ["x_thread"]})
    job_id = created.json()["id"]
    wait_for(job_id)
    assert operator.post(f"/api/jobs/{job_id}/submit", json={}).status_code == 200
    monkeypatch.setattr(settings, "export_timeout_seconds", 0.5)
    response = reviewer.post(f"/api/jobs/{job_id}/review", json={"decision": "approve"})
    assert response.status_code == 504 and response.json()["detail"].startswith("Could not sign:")
    job = operator.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "in_review" and not job.get("record_no")


def test_same_file_saved_by_two_downloads_at_once(tmp_path):
    """Two downloads of the same file at the same moment used to collide on one temporary name (an error 500)."""
    target = tmp_path / "exports" / "job1-infographic-ta.png"
    errors = []

    def save(n):
        try:
            for _ in range(30):
                crypto.write_file(target, bytes([n]) * 1000)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=save, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(set(crypto.read_file(target))) == 1  # one whole file, not a mix
    assert [p.name for p in target.parent.iterdir()] == [target.name]  # no temporary files left behind
