"""Stage 8 part 6: the interface in English and Hindi. Every text the app shows through t() must have Hindi in
frontend/src/i18n/hi.json (the check runs frontend/scripts/i18n-keys.cjs with Node), and the app language is
saved per user."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.auth_helpers import signed_in_client

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_every_interface_text_has_hindi():
    result = subprocess.run(["node", "scripts/i18n-keys.cjs", "--check"], cwd=FRONTEND, capture_output=True, text=True,
                            timeout=180)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "have Hindi" in result.stdout


def test_the_app_language_is_saved_per_user():
    hindi = signed_in_client("operator", "i18n.hindi")
    english = signed_in_client("operator", "i18n.english")
    assert hindi.put("/api/profile", json={"language": "hi"}).json()["user"]["language"] == "hi"
    assert hindi.get("/api/auth/me").json()["user"]["language"] == "hi"
    assert english.get("/api/auth/me").json()["user"]["language"] == "en"
