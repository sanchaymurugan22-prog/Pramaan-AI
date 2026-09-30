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
    # "local" = llama.cpp on this computer, "cloud" = Sarvam hosted API (dev fallback)
    ai_mode: str = _get("AI_MODE", "local").lower()

    # local llama.cpp server
    llm_base_url: str = _get("LLM_BASE_URL", "http://localhost:8081/v1")
    llm_model: str = _get("LLM_MODEL", "sarvam-30b")

    # Sarvam hosted API
    sarvam_base_url: str = _get("SARVAM_BASE_URL", "https://api.sarvam.ai/v1")
    sarvam_model: str = _get("SARVAM_MODEL", "sarvam-105b")
    sarvam_api_key: str = _get("SARVAM_API_KEY")

    llm_timeout_seconds: float = float(_get("LLM_TIMEOUT_SECONDS", "300"))

    # where the database, uploads and outputs live
    data_dir: Path = (PROJECT_ROOT / _get("DATA_DIR", "./data")).resolve()


settings = Settings()
