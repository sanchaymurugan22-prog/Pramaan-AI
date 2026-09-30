"""Test setup: runs before any test file is imported.

Tests always use the mock AI (instant answers built from the source, no model needed) and a temporary data
folder, so they never touch the real data/ folder or database.
"""

import os
import tempfile

os.environ["AI_MODE"] = "mock"
os.environ["MOCK_DELAY_SECONDS"] = "0"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pramaan-test-")
# Test-only secrets, so the tests never write new ones into the real .env
os.environ["APP_SECRET_KEY"] = "test-" + "0" * 59
# the TestClient's own address counts as one of our pages (see check_origin in app/main.py)
os.environ["ALLOWED_ORIGINS"] = "http://testserver,https://testserver,http://localhost:5173"

from app.db import init_db  # noqa: E402  (must come after the environment is set)

init_db()
