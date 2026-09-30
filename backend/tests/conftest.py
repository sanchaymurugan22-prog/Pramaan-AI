"""Test setup: runs before any test file is imported.

Tests always use the mock AI (instant canned answers, no model needed) and a temporary data
folder, so they never touch the real data/ folder or database.
"""

import os
import tempfile

os.environ["AI_MODE"] = "mock"
os.environ["MOCK_DELAY_SECONDS"] = "0"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pramaan-test-")

from app.db import init_db  # noqa: E402  (must come after the environment is set)

init_db()
