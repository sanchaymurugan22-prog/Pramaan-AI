"""Stage 7 part 3: the public verify bundle. What records.json publishes (and does not), the zip, and the
page's own JavaScript (verify-page/verify.js), run with Node against a real published site."""

import hashlib
import io
import json
import os
import shutil
import subprocess
import zipfile

import pytest

from app import crypto
from app.db import Record, SessionLocal
from app.signing import publish, records
from app.signing.sign_job import signed_dir
from app.signing.signer import get_signer, verify
from tests.auth_helpers import signed_in_client
from tests.test_signing import approved_job, operator, reviewer

admin = signed_in_client("admin", "verify.admin")


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> dict:
    """Genuine (GREEN), restricted (RED), replaced and withdrawn records, published into a folder."""
    genuine = approved_job(outputs=("x_thread", "advisory"), tlp="GREEN")
    restricted = approved_job(outputs=("advisory",), tlp="RED", title="Operation Kestrel internal briefing")
    replaced = approved_job(outputs=("x_thread",))
    operator.post(f"/api/jobs/{replaced['id']}/new-version")
    operator.post(f"/api/jobs/{replaced['id']}/submit", json={})
    replacement = reviewer.post(f"/api/jobs/{replaced['id']}/review", json={"decision": "approve"}).json()
    withdrawn = approved_job(outputs=("x_thread",))
    reason = "Superseded by the CERT-In update"
    assert admin.post(f"/api/admin/records/{withdrawn['record']['record_no']}/withdraw",
                      json={"reason": reason}).status_code == 200

    folder = tmp_path_factory.mktemp("verify-site")
    with SessionLocal() as db:
        publish.build_site(db, folder / "site")
        issued = db.query(Record).filter_by(kind="issue").count()

    files_dir = folder / "files"
    files_dir.mkdir()
    for job in (genuine, withdrawn):
        for f in job["record"]["files"]:
            (files_dir / f["name"]).write_bytes(crypto.read_file(signed_dir(job["id"], job["record"]["record_no"]) / f["name"]))
    pdf = next(f["name"] for f in genuine["record"]["files"] if f["name"].endswith(".pdf"))
    fixture = {
        "issued": issued,
        "genuine": genuine["record"]["record_no"],
        "restricted": restricted["record"]["record_no"],
        "restricted_title": restricted["title"],
        "replaced": replaced["record"]["record_no"],
        "replacement": replacement["record"]["record_no"],
        "withdrawn": withdrawn["record"]["record_no"],
        "withdraw_reason": reason,
        "signed_file": pdf,
        "withdrawn_file": withdrawn["record"]["files"][0]["name"],
        "files_dir": str(files_dir),
        "big_sha256": hashlib.sha256(bytes((i * 31) % 251 for i in range(200_003))).hexdigest(),
    }
    (folder / "fixture.json").write_text(json.dumps(fixture))
    return {"folder": folder / "site", "fixture_path": folder / "fixture.json", **fixture}


def test_the_site_has_the_page_records_and_key_but_no_tests(site):
    names = {p.relative_to(site["folder"]).as_posix() for p in site["folder"].rglob("*") if p.is_file()}
    assert {"index.html", "app.js", "verify.js", "style.css", "sw.js", "records.json", "public-key.pem"} <= names
    assert not any(n.startswith("tests/") for n in names)
    assert (site["folder"] / "public-key.pem").read_text() == get_signer().public_key_pem()


def test_records_json_publishes_only_public_parts(site):
    data = json.loads((site["folder"] / "records.json").read_text())
    text = json.dumps(data, ensure_ascii=False)
    for secret in ("user_id", "job_id", "Sign Reviewer", "Verify Admin", "PRIVATE KEY"):
        assert secret not in text
    assert site["restricted_title"] not in text  # TLP:RED: no title anywhere
    assert "Superseded by the CERT-In update" in text  # a GREEN record's withdrawal reason is public

    key = get_signer().public_key_pem()
    assert verify(key, data["index"].encode(), data["index_signature"])
    index = json.loads(data["index"])
    assert index["count"] == len(data["entries"])
    assert index["entries"] == [hashlib.sha256(e["manifest"].encode()).hexdigest() for e in data["entries"]]
    with SessionLocal() as db:
        assert index["chain_head"] == records.last_entry(db).entry_hash
    assert all(verify(key, e["manifest"].encode(), e["signature"]) for e in data["entries"])


def test_the_admin_exports_the_bundle_as_a_zip(site):
    response = admin.get("/api/admin/records/verify-bundle.zip")
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    names = set(zipfile.ZipFile(io.BytesIO(response.content)).namelist())
    assert {"verify-site/index.html", "verify-site/records.json", "verify-site/public-key.pem",
            "verify-site/HOW-TO-PUBLISH.txt"} <= names
    assert not any("/tests/" in n for n in names)


def test_the_demo_site_is_refreshed_after_signing(site, monkeypatch, tmp_path):
    demo = tmp_path / "verify-site"
    demo.mkdir()
    monkeypatch.setattr(publish, "DEMO_SITE", demo)
    job = approved_job(outputs=("x_thread",))
    assert job["record"]["record_no"] in (demo / "records.json").read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_the_verify_page_javascript(site):
    """verify-page/tests/verify.test.mjs: signatures, lookups, file check, tampering, with and without Web Crypto."""
    project = publish.VERIFY_PAGE.parent
    result = subprocess.run(
        ["node", "--test", str(publish.VERIFY_PAGE / "tests" / "verify.test.mjs")], cwd=project, capture_output=True, text=True, timeout=180,
        env=os.environ | {"VERIFY_SITE": str(site["folder"]), "VERIFY_FIXTURE": str(site["fixture_path"])},
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    assert "# fail 0" in result.stdout
