"""App settings, read from the .env file in the project root.

Every other module imports `settings` from here instead of reading
environment variables itself, so there is one place to look.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> project root is two folders up from backend/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from the project root. Real environment variables win over .env.
load_dotenv(PROJECT_ROOT / ".env")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class Settings:
    # "local" = llama.cpp on this computer, "cloud" = Sarvam hosted API (dev fallback),
    # "mock" = instant canned answers, for testing the UI without any model
    ai_mode: str = _get("AI_MODE", "local").lower()

    # mock mode only: pretend each answer takes this many seconds (0 = instant)
    mock_delay_seconds: float = float(_get("MOCK_DELAY_SECONDS", "0"))

    # local llama.cpp server
    llm_base_url: str = _get("LLM_BASE_URL", "http://localhost:8081/v1")
    llm_model: str = _get("LLM_MODEL", "sarvam-30b")

    # Sarvam hosted API
    sarvam_base_url: str = _get("SARVAM_BASE_URL", "https://api.sarvam.ai/v1")
    sarvam_model: str = _get("SARVAM_MODEL", "sarvam-105b")
    sarvam_api_key: str = _get("SARVAM_API_KEY")

    llm_timeout_seconds: float = float(_get("LLM_TIMEOUT_SECONDS", "600"))

    # Long sources are split into pieces of about this many characters, so each piece fits in the
    # model's 4096-token context together with the instructions and the answer (~4 characters per token).
    factsheet_chunk_chars: int = int(_get("FACTSHEET_CHUNK_CHARS", "6000"))

    # How many key facts to ask for (per chunk when the source is split). Fewer = faster.
    # Never more than 8: with more, the local model ran out of tokens before finishing the JSON.
    factsheet_max_facts: int = min(int(_get("FACTSHEET_MAX_FACTS", "8")), 8)

    # where the database, uploads and outputs live
    data_dir: Path = (PROJECT_ROOT / _get("DATA_DIR", "./data")).resolve()


settings = Settings()


# Most tokens the model may write for each kind of answer. The local model writes about
# 1.4 tokens/second, so 350 tokens is about 4 minutes. Override any of these in .env,
# e.g. MAX_TOKENS_X_THREAD=250
DEFAULT_MAX_TOKENS = {
    "factsheet": 1400,  # was 1100: the local fact sheet was cut off at the limit
    "x_thread": 350,
    "linkedin_post": 350,
    "executive_summary": 450,
    "infographic": 400,
    "advisory": 800,
    "presentation": 900,
    "video_package": 900,
}


def max_tokens_for(kind: str) -> int:
    """Token limit for one kind of answer: MAX_TOKENS_<KIND> from .env, or the default above."""
    return int(_get(f"MAX_TOKENS_{kind.upper()}", str(DEFAULT_MAX_TOKENS.get(kind, 400))))
