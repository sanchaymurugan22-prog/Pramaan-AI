"""App settings, read from the .env file in the project root.

Every other module imports `settings` from here instead of reading
environment variables itself, so there is one place to look.
"""

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> project root is two folders up from backend/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Load .env from the project root. Real environment variables win over .env.
load_dotenv(ENV_FILE)

log = logging.getLogger("pramaan.config")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def ensure_secret(name: str, env_file: Path = ENV_FILE) -> str:
    """The value of a secret setting (APP_SECRET_KEY, DB_KEY). If it is empty, make a new random one
    (256 bits) and save it in .env, so it stays the same after a restart. The value is never printed
    or logged, only the fact that a new one was made."""
    value = _get(name)
    if value:
        return value
    value = secrets.token_hex(32)
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    for number, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == name:
            lines[number] = f"{name}={value}"
            break
    else:
        lines.append(f"{name}={value}")
    # Write a new file (readable by this user only), then swap it in, so .env is never half-written.
    temporary = env_file.with_name(env_file.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    os.replace(temporary, env_file)
    os.environ[name] = value
    log.warning("%s was empty, so a new random one was made and saved in .env", name)
    return value


class Settings:
    # "local" = llama.cpp on this computer, "cloud" = Sarvam hosted API (dev fallback),
    # "mock" = instant answers built from the source by simple rules, for testing without any model
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

    # --- sign-in (Stage 6B) ---
    # Key for the sign-in session fingerprints. Made on first run if empty (see ensure_secret).
    app_secret_key: str = ensure_secret("APP_SECRET_KEY")
    # Web pages allowed to send changes (POST/PUT/DELETE) to the API: the Vite dev server and the
    # backend itself. Anything else (another website open in the same browser) is refused.
    allowed_origins: frozenset[str] = frozenset(
        o.strip().rstrip("/") for o in _get(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",") if o.strip()
    )


    # --- languages and voice (Stage 8) ---
    # Where the downloaded models live (scripts/download-models.py puts them there).
    models_dir: Path = (PROJECT_ROOT / _get("MODELS_DIR", "./models")).resolve()
    # indictrans2 = AI4Bharat IndicTrans2 on this computer | llm = through the AI model (llm.py) | mock = tests
    translate_engine: str = _get("TRANSLATE_ENGINE", "indictrans2").lower()
    translate_threads: int = int(_get("TRANSLATE_THREADS", "4"))
    # piper = Piper voices (sherpa-onnx), macOS "say" for languages without one | say = macOS only | mock = tests
    tts_engine: str = _get("TTS_ENGINE", "piper").lower()
    # onnx = IndicConformer (Hindi, Tamil) and Whisper small (English) | mock = tests
    stt_engine: str = _get("STT_ENGINE", "onnx").lower()

    # --- exports (files made from outputs) ---
    # Files are made by a small pool of export workers (never by the web server's own loop), each with a time
    # limit: a file that takes longer gives a clear error instead of a page that never loads.
    export_workers: int = max(1, int(_get("EXPORT_WORKERS", "2")))
    export_timeout_seconds: float = float(_get("EXPORT_TIMEOUT_SECONDS", "120"))
    # Video (.mp4) and narration (.mp3) read the script aloud first, which takes minutes on a slow laptop
    media_export_timeout_seconds: float = float(_get("MEDIA_EXPORT_TIMEOUT_SECONDS", "900"))

    # --- watch folder (Stage 9A) ---
    # How often switched-on watch folders (inside data/watch/) are checked for new files. 0 = never.
    watch_interval_seconds: float = float(_get("WATCH_INTERVAL_SECONDS", "60"))

    # --- signing and verification (Stage 7) ---
    # The public "Is this real?" page. The QR code on every signed file holds <this>/?r=<record number>.
    # To scan it with a phone on the same Wi-Fi, use this Mac's address, e.g. http://192.168.1.20:8090
    verify_base_url: str = _get("VERIFY_BASE_URL", "http://localhost:8090").rstrip("/")
    # Printed on the verify page as "Issued by"
    issuing_office: str = _get("ISSUING_OFFICE", "Pramaan AI demo office")
    # test = a key made on this computer (for development); dsc = a Class 3 DSC USB token (design only, not tested)
    signer: str = _get("SIGNER", "test").lower()
    # dsc only: the token maker's PKCS#11 library and the key's label on the token
    pkcs11_lib: str = _get("PKCS11_LIB")
    dsc_key_label: str = _get("DSC_KEY_LABEL")


settings = Settings()


# Most tokens the model may write for each kind of answer. The local model writes about
# 1.4 tokens/second, so 350 tokens is about 4 minutes. Override any of these in .env,
# e.g. MAX_TOKENS_X_THREAD=250
DEFAULT_MAX_TOKENS = {
    "factsheet": 3500,  # was 1400: raised to avoid cutoff when generating fact sheet
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
